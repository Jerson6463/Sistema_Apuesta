"""
Servicios de negocio para la gestión de apuestas.

Flujo principal:
  crear_apuesta() → valida → bloquea fondos (wallet) → crea Apuesta(ACEPTADA)
  liquidar_apuesta() → cambia estado FSM → mueve fondos según resultado
  anular_apuesta() → devuelve stake → estado ANULADA
"""
import uuid
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
)


# ── Validaciones ───────────────────────────────────────────────────────────────

def _validar_usuario(usuario):
    if not usuario.puede_apostar():
        raise UsuarioNoHabilitadoError(
            f"El usuario {usuario.username} no está habilitado para apostar "
            f"(estado: {usuario.estado})."
        )


def _validar_mercado(mercado):
    if mercado.estado != EstadoMercado.ABIERTO:
        raise MercadoCerradoError(
            f"El mercado '{mercado.get_tipo_display()}' no está abierto."
        )


def _validar_evento_simple(evento):
    if evento.estado != EstadoEvento.PROGRAMADO:
        raise EventoNoDisponibleError(
            f"El evento '{evento.nombre}' no acepta apuestas simples "
            f"(estado: {evento.estado}). Debe estar PROGRAMADO."
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
    pago_potencial = monto * cuota_snapshot

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
    """
    if apuesta.estado != EstadoApuesta.ACEPTADA:
        raise CashOutNoDisponibleError(
            f"Cash-out no disponible para apuesta en estado {apuesta.estado}."
        )

    odds_actual = apuesta.cuota.valor
    if odds_actual <= Decimal("0"):
        raise CashOutNoDisponibleError("La cuota actual es inválida para cash-out.")

    monto_cash_out = (
        apuesta.monto_apostado
        * apuesta.cuota_al_apostar
        / odds_actual
        * factor_casa
    ).quantize(Decimal("0.0001"))

    apuesta.marcar_cash_out()
    apuesta.save()

    # Devolver el monto de cash-out (liberar stake bloqueado + pagar cash-out neto)
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
        ip_origen=ip_origen,
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