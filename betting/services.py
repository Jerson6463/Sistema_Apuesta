"""
Servicios de negocio para la gestión de apuestas.

Flujo principal:
  crear_apuesta() → valida → bloquea fondos (wallet) → crea Apuesta(ACEPTADA)
  liquidar_apuesta() → cambia estado FSM → mueve fondos según resultado
  anular_apuesta() → devuelve stake → estado ANULADA
"""
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from betting.exceptions import (
    ApuestaYaLiquidadaError,
    CashOutNoDisponibleError,
    EventoNoDisponibleError,
    MercadoCerradoError,
    MontoFueraDeRangoError,
    SeleccionMutuamenteExcluyenteError,
    UsuarioNoHabilitadoError,
    SaldoInsuficienteApuestaError,
)
from betting.models import (
    Apuesta, ApuestaCombinada, Cuota, EstadoApuesta,
    EstadoEvento, EstadoMercado, HistorialCuota,
)
from wallet.exceptions import SaldoInsuficienteError
from wallet.services import (
    bloquear_fondos_apuesta,
    devolver_apuesta_anulada,
    liberar_fondos_ganancia,
    liberar_fondos_perdida,
    obtener_saldo,
    quantizar_monto,
)


# ── Validaciones ───────────────────────────────────────────────────────────────

# Cierre prematch 1 minuto antes del inicio (evita apuestas en el último instante).
MARGEN_CIERRE_PREMATCH = timedelta(minutes=1)


def _a_utc(fecha: datetime) -> datetime:
    """Normaliza datetimes conscientes de zona horaria a UTC para comparaciones."""
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, dt_timezone.utc)
    return fecha.astimezone(dt_timezone.utc)


def _validar_usuario(usuario):
    if not usuario.puede_apostar():
        raise UsuarioNoHabilitadoError(
            f"El usuario {usuario.username} no está habilitado para apostar "
            f"(estado: {usuario.estado})."
        )


def _validar_mercado(mercado):
    if mercado.estado == EstadoMercado.SUSPENDIDO:
        raise MercadoCerradoError(
            f"El mercado '{mercado.get_tipo_display()}' está suspendido temporalmente. "
            f"Intente en unos segundos."
        )
    if mercado.estado != EstadoMercado.ABIERTO:
        raise MercadoCerradoError(
            f"El mercado '{mercado.get_tipo_display()}' no está abierto "
            f"(estado: {mercado.estado})."
        )


def _validar_evento_simple(evento):
    """
    Validación prematch para apuestas simples y combinadas.

    Reglas:
      1. Estado prematch (= PROGRAMADO en nuestro FSM). Rechaza EN_VIVO,
         FINALIZADO, SUSPENDIDO y ANULADO.
      2. Comparación temporal en UTC: timezone.now() debe ser estrictamente
         anterior a evento.fecha_inicio, con margen de cierre de 1 minuto
         para evitar apuestas en el último instante antes del kick-off.

    Protección de zona horaria:
      Django persiste datetimes en UTC (USE_TZ=True). Normalizamos ambos
      instantes a UTC con _a_utc() antes de comparar, evitando errores por
      offsets locales o datetimes naive.
    """
    if evento.estado == EstadoEvento.EN_VIVO:
        raise EventoNoDisponibleError(
            f"El evento '{evento.nombre}' está EN VIVO. "
            f"Las apuestas prematch no están permitidas; use el endpoint in-play."
        )

    if evento.estado != EstadoEvento.PROGRAMADO:
        raise EventoNoDisponibleError(
            f"El evento '{evento.nombre}' no acepta apuestas prematch "
            f"(estado: {evento.get_estado_display()}). "
            f"Solo se permiten eventos en estado PROGRAMADO (prematch)."
        )

    ahora_utc = _a_utc(timezone.now())
    inicio_utc = _a_utc(evento.fecha_inicio)
    cierre_prematch = inicio_utc - MARGEN_CIERRE_PREMATCH

    if ahora_utc >= cierre_prematch:
        raise EventoNoDisponibleError(
            f"El evento '{evento.nombre}' ya no acepta apuestas prematch "
            f"(inicio UTC: {inicio_utc.isoformat()}, "
            f"margen de cierre: {MARGEN_CIERRE_PREMATCH.total_seconds():.0f}s)."
        )


def _validar_monto(monto: Decimal, mercado):
    if monto < mercado.monto_minimo:
        raise MontoFueraDeRangoError(
            f"El monto mínimo para este mercado es {mercado.monto_minimo}."
        )
    if monto > mercado.monto_maximo:
        raise MontoFueraDeRangoError(
            f"El monto máximo para este mercado es {mercado.monto_maximo}."
        )


def _validar_saldo(usuario, monto: Decimal):
    if obtener_saldo(usuario) < monto:
        raise SaldoInsuficienteApuestaError(
            f"Saldo insuficiente. Disponible: {obtener_saldo(usuario)}, "
            f"solicitado: {monto}."
        )


# ── Apuesta simple ────────────────────────────────────────────────────────────

@transaction.atomic
def crear_apuesta(
    *,
    usuario,
    cuota: Cuota,
    monto: Decimal,
    clave_idempotencia: uuid.UUID,
    ip_origen: str = None,
) -> Apuesta:
    """
    Crea y confirma una apuesta simple.
    Si la clave_idempotencia ya existe, devuelve la apuesta existente sin duplicar.
    """
    try:
        return Apuesta.objects.get(clave_idempotencia=clave_idempotencia)
    except Apuesta.DoesNotExist:
        pass

    mercado = cuota.mercado
    evento = mercado.evento

    _validar_usuario(usuario)
    _validar_mercado(mercado)
    _validar_evento_simple(evento)
    _validar_monto(monto, mercado)
    _validar_saldo(usuario, monto)

    cuota_snapshot = cuota.valor
    pago_potencial = quantizar_monto(monto * cuota_snapshot)

    apuesta = Apuesta.objects.create(
        usuario=usuario,
        cuota=cuota,
        monto_apostado=monto,
        cuota_al_apostar=cuota_snapshot,
        pago_potencial=pago_potencial,
        clave_idempotencia=clave_idempotencia,
        ip_origen=ip_origen,
    )

    bloquear_fondos_apuesta(
        usuario,
        monto,
        id_transaccion=uuid.uuid5(clave_idempotencia, "bloqueo"),
        referencia_id=apuesta.id,
    )

    return apuesta


@transaction.atomic
def liquidar_apuesta(apuesta: Apuesta, *, resultado_ganador: str) -> None:
    """
    Liquida una apuesta comparando la selección elegida con el resultado.
    resultado_ganador: valor de Cuota.seleccion del resultado real.
    """
    if apuesta.estado not in (EstadoApuesta.ACEPTADA,):
        raise ApuestaYaLiquidadaError(
            f"La apuesta {apuesta.id} ya fue liquidada (estado: {apuesta.estado})."
        )

    seleccion_apostada = apuesta.cuota.seleccion

    if seleccion_apostada == resultado_ganador:
        apuesta.marcar_ganada()
        apuesta.save()
        liberar_fondos_ganancia(
            apuesta.usuario,
            apuesta.monto_apostado,
            apuesta.cuota_al_apostar,
            id_apuesta=apuesta.id,
        )
    else:
        apuesta.marcar_perdida()
        apuesta.save()
        liberar_fondos_perdida(
            apuesta.usuario,
            apuesta.monto_apostado,
            id_apuesta=apuesta.id,
        )


@transaction.atomic
def anular_apuesta(apuesta: Apuesta) -> None:
    """Anula una apuesta y devuelve el stake al usuario."""
    if apuesta.estado != EstadoApuesta.ACEPTADA:
        raise ApuestaYaLiquidadaError(
            f"No se puede anular la apuesta {apuesta.id} (estado: {apuesta.estado})."
        )
    apuesta.marcar_anulada()
    apuesta.save()
    devolver_apuesta_anulada(
        apuesta.usuario,
        apuesta.monto_apostado,
        id_apuesta=apuesta.id,
    )


@transaction.atomic
def hacer_cash_out(apuesta: Apuesta, *, factor_casa: Decimal = Decimal("0.9000")) -> Decimal:
    """
    Cierra anticipadamente una apuesta aceptada.
    Fórmula: cashout = stake × odds_original / odds_actual × factor_casa

    Concurrencia + FSM:
      - select_for_update().get() relee la apuesta bajo bloqueo de fila sin
        refresh_from_db(), evitando el setter protegido de FSMField.
      - La cuota se bloquea por separado para leer la odds más reciente in-play.
      - El estado solo cambia vía apuesta.marcar_cash_out() (transición FSM).
    """
    apuesta_id = apuesta.pk

    # Evaluación inmediata del QS → SELECT … FOR UPDATE en PostgreSQL.
    apuesta = (
        Apuesta.objects.select_for_update()
        .select_related("cuota")
        .get(pk=apuesta_id)
    )

    if apuesta.estado != EstadoApuesta.ACEPTADA:
        raise CashOutNoDisponibleError(
            f"Cash-out no disponible para apuesta en estado {apuesta.estado}."
        )

    # Bloqueo adicional sobre la cuota: odds in-play cambian en milisegundos.
    cuota = Cuota.objects.select_for_update().get(pk=apuesta.cuota_id)
    odds_actual = cuota.valor
    if odds_actual <= Decimal("0"):
        raise CashOutNoDisponibleError("La cuota actual es inválida para cash-out.")

    monto_cash_out = (
        apuesta.monto_apostado
        * apuesta.cuota_al_apostar
        / odds_actual
        * factor_casa
    ).quantize(Decimal("0.0001"))

    # Única vía válida para mutar estado con protected=True en el FSMField.
    apuesta.marcar_cash_out()
    apuesta.save()

    # Movimientos de wallet (ya resuelven concurrencia con _bloquear_entradas_usuario).
    devolver_apuesta_anulada(
        apuesta.usuario,
        apuesta.monto_apostado,
        id_apuesta=uuid.uuid5(apuesta.id, "cash_out_stake"),
    )
    if monto_cash_out > apuesta.monto_apostado:
        ganancia = monto_cash_out - apuesta.monto_apostado
        from wallet.models import TipoCuenta, DireccionMovimiento, TipoReferencia, EntradaContable
        id_tx_ganancia = uuid.uuid5(apuesta.id, "cash_out_ganancia")
        EntradaContable.objects.create(
            cuenta=TipoCuenta.CASA,
            usuario=None,
            monto=ganancia,
            direccion=DireccionMovimiento.DEBITO,
            id_transaccion=id_tx_ganancia,
            tipo_referencia=TipoReferencia.CASH_OUT,
            referencia_id=apuesta.id,
        )
        EntradaContable.objects.create(
            cuenta=TipoCuenta.WALLET_USUARIO,
            usuario=apuesta.usuario,
            monto=ganancia,
            direccion=DireccionMovimiento.CREDITO,
            id_transaccion=id_tx_ganancia,
            tipo_referencia=TipoReferencia.CASH_OUT,
            referencia_id=apuesta.id,
        )

    return monto_cash_out


# ── Apuesta combinada ─────────────────────────────────────────────────────────

def _validar_selecciones_combinada(cuotas: list[Cuota]) -> None:
    """Las selecciones de un mismo mercado son mutuamente excluyentes."""
    mercados_vistos = {}
    for cuota in cuotas:
        mid = cuota.mercado_id
        if mid in mercados_vistos:
            raise SeleccionMutuamenteExcluyenteError(
                f"No puedes combinar dos selecciones del mismo mercado "
                f"(mercado id={mid})."
            )
        mercados_vistos[mid] = cuota.seleccion


@transaction.atomic
def crear_apuesta_combinada(
    *,
    usuario,
    cuotas: list[Cuota],
    monto: Decimal,
    clave_idempotencia: uuid.UUID,
    ip_origen: str = None,
) -> ApuestaCombinada:
    """
    Crea una apuesta acumuladora. Cuota total = producto de cuotas individuales.
    Si cualquier selección pierde, toda la combinada pierde.
    """
    try:
        return ApuestaCombinada.objects.get(clave_idempotencia=clave_idempotencia)
    except ApuestaCombinada.DoesNotExist:
        pass

    _validar_usuario(usuario)
    _validar_selecciones_combinada(cuotas)

    for cuota in cuotas:
        _validar_mercado(cuota.mercado)
        _validar_evento_simple(cuota.mercado.evento)

    cuota_total = Decimal("1.0000")
    for cuota in cuotas:
        cuota_total *= cuota.valor

    _validar_saldo(usuario, monto)

    combinada = ApuestaCombinada.objects.create(
        usuario=usuario,
        monto_apostado=monto,
        cuota_total=cuota_total,
        pago_potencial=monto * cuota_total,
        clave_idempotencia=clave_idempotencia,
    )
    combinada.selecciones.set(cuotas)

    bloquear_fondos_apuesta(
        usuario,
        monto,
        id_transaccion=uuid.uuid5(clave_idempotencia, "bloqueo_combinada"),
        referencia_id=combinada.id,
    )

    return combinada


def registrar_cambio_cuota(cuota: Cuota, nuevo_valor: Decimal) -> None:
    """Registra el historial, actualiza la cuota y notifica via WebSocket."""
    valor_anterior = cuota.valor
    HistorialCuota.objects.create(
        cuota=cuota,
        valor_anterior=valor_anterior,
        valor_nuevo=nuevo_valor,
    )
    cuota.valor = nuevo_valor
    cuota.save(update_fields=["valor", "actualizado_en"])

    # Notificar a suscriptores WebSocket de forma asíncrona (no bloquea la request)
    from betting.tasks import publicar_actualizacion_cuota
    publicar_actualizacion_cuota.delay(
        evento_id=cuota.mercado.evento_id,
        cuota_id=cuota.id,
        seleccion=cuota.seleccion,
        valor_anterior=str(valor_anterior),
        valor_nuevo=str(nuevo_valor),
    )
