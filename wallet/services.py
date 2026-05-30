"""
Servicios de wallet con partida doble.

Reglas de negocio:
- Toda operación se ejecuta dentro de una transacción atómica con select_for_update.
- El saldo NUNCA se almacena; siempre se calcula con obtener_saldo().
- Cada operación crea exactamente dos EntradaContable balanceadas (suma neta = 0).
- Las idempotency keys (id_transaccion) evitan doble procesamiento.
"""
import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from wallet.exceptions import (
    CuentaNoVerificadaError,
    LimiteSuperadoError,
    SaldoInsuficienteError,
    TransaccionDuplicadaError,
)
from wallet.models import (
    DireccionMovimiento,
    EntradaContable,
    TipoCuenta,
    TipoReferencia,
)


# ── Lectura de saldo ───────────────────────────────────────────────────────────

def obtener_saldo(usuario) -> Decimal:
    """Calcula el saldo disponible (wallet_usuario creditos - debitos)."""
    qs = EntradaContable.objects.filter(
        usuario=usuario,
        cuenta=TipoCuenta.WALLET_USUARIO,
    )
    creditos = qs.filter(direccion=DireccionMovimiento.CREDITO).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0")
    debitos = qs.filter(direccion=DireccionMovimiento.DEBITO).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0")
    return creditos - debitos


def obtener_saldo_bloqueado(usuario) -> Decimal:
    """Fondos en apuestas_pendientes del usuario."""
    qs = EntradaContable.objects.filter(
        usuario=usuario,
        cuenta=TipoCuenta.APUESTAS_PENDIENTES,
    )
    creditos = qs.filter(direccion=DireccionMovimiento.CREDITO).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0")
    debitos = qs.filter(direccion=DireccionMovimiento.DEBITO).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0")
    return creditos - debitos


def verificar_balance_transaccion(id_transaccion: uuid.UUID) -> bool:
    """Verifica que la suma neta de una transacción sea cero."""
    entradas = EntradaContable.objects.filter(id_transaccion=id_transaccion)
    total = Decimal("0")
    for entrada in entradas:
        if entrada.direccion == DireccionMovimiento.CREDITO:
            total += entrada.monto
        else:
            total -= entrada.monto
    return total == Decimal("0")


# ── Helpers internos ───────────────────────────────────────────────────────────

def _transaccion_ya_procesada(id_transaccion: uuid.UUID) -> bool:
    return EntradaContable.objects.filter(id_transaccion=id_transaccion).exists()


def _crear_par_contable(
    *,
    cuenta_debito: str,
    cuenta_credito: str,
    usuario_debito,
    usuario_credito,
    monto: Decimal,
    id_transaccion: uuid.UUID,
    tipo_referencia: str,
    referencia_id: uuid.UUID = None,
):
    """Crea el par mínimo de entradas (débito + crédito) de forma atómica."""
    EntradaContable.objects.create(
        cuenta=cuenta_debito,
        usuario=usuario_debito,
        monto=monto,
        direccion=DireccionMovimiento.DEBITO,
        id_transaccion=id_transaccion,
        tipo_referencia=tipo_referencia,
        referencia_id=referencia_id,
    )
    EntradaContable.objects.create(
        cuenta=cuenta_credito,
        usuario=usuario_credito,
        monto=monto,
        direccion=DireccionMovimiento.CREDITO,
        id_transaccion=id_transaccion,
        tipo_referencia=tipo_referencia,
        referencia_id=referencia_id,
    )


def _verificar_limite_diario(usuario, monto: Decimal):
    from users.models import LimiteJuego
    from django.utils import timezone

    limite = LimiteJuego.objects.get(usuario=usuario)
    hoy = timezone.now().date()
    recargado_hoy = (
        EntradaContable.objects.filter(
            usuario=usuario,
            cuenta=TipoCuenta.WALLET_USUARIO,
            direccion=DireccionMovimiento.CREDITO,
            tipo_referencia=TipoReferencia.RECARGA,
            creado_en__date=hoy,
        ).aggregate(total=Sum("monto"))["total"]
        or Decimal("0")
    )
    if recargado_hoy + monto > limite.limite_diario:
        raise LimiteSuperadoError(
            f"Superas el límite diario de fichas ({limite.limite_diario}). "
            f"Ya recargaste {recargado_hoy} hoy."
        )


def _verificar_limite_semanal(usuario, monto: Decimal):
    from users.models import LimiteJuego
    from django.utils import timezone

    limite = LimiteJuego.objects.get(usuario=usuario)
    inicio_semana = timezone.now().date() - timezone.timedelta(days=timezone.now().weekday())
    recargado_semana = (
        EntradaContable.objects.filter(
            usuario=usuario,
            cuenta=TipoCuenta.WALLET_USUARIO,
            direccion=DireccionMovimiento.CREDITO,
            tipo_referencia=TipoReferencia.RECARGA,
            creado_en__date__gte=inicio_semana,
        ).aggregate(total=Sum("monto"))["total"]
        or Decimal("0")
    )
    if recargado_semana + monto > limite.limite_semanal:
        raise LimiteSuperadoError(
            f"Superas el límite semanal de fichas ({limite.limite_semanal}). "
            f"Ya recargaste {recargado_semana} esta semana."
        )


def _verificar_limite_mensual(usuario, monto: Decimal):
    from users.models import LimiteJuego
    from django.utils import timezone

    limite = LimiteJuego.objects.get(usuario=usuario)
    ahora = timezone.now()
    recargado_mes = (
        EntradaContable.objects.filter(
            usuario=usuario,
            cuenta=TipoCuenta.WALLET_USUARIO,
            direccion=DireccionMovimiento.CREDITO,
            tipo_referencia=TipoReferencia.RECARGA,
            creado_en__year=ahora.year,
            creado_en__month=ahora.month,
        ).aggregate(total=Sum("monto"))["total"]
        or Decimal("0")
    )
    if recargado_mes + monto > limite.limite_mensual:
        raise LimiteSuperadoError(
            f"Superas el límite mensual de fichas ({limite.limite_mensual}). "
            f"Ya recargaste {recargado_mes} este mes."
        )


# ── Operaciones públicas ───────────────────────────────────────────────────────

@transaction.atomic
def recargar_fichas(
    usuario,
    monto: Decimal,
    *,
    id_transaccion: uuid.UUID,
) -> None:
    """
    Simula una recarga de fichas virtuales.
    Partida: DEBITO casa → CREDITO wallet_usuario
    """
    if _transaccion_ya_procesada(id_transaccion):
        return  # idempotencia

    _verificar_limite_diario(usuario, monto)
    _verificar_limite_semanal(usuario, monto)
    _verificar_limite_mensual(usuario, monto)

    # select_for_update sobre las entradas del usuario para evitar condiciones de carrera
    EntradaContable.objects.select_for_update().filter(usuario=usuario)

    _crear_par_contable(
        cuenta_debito=TipoCuenta.CASA,
        cuenta_credito=TipoCuenta.WALLET_USUARIO,
        usuario_debito=None,
        usuario_credito=usuario,
        monto=monto,
        id_transaccion=id_transaccion,
        tipo_referencia=TipoReferencia.RECARGA,
    )


@transaction.atomic
def retirar_fichas(
    usuario,
    monto: Decimal,
    *,
    id_transaccion: uuid.UUID,
) -> None:
    """
    Simula un retiro de fichas virtuales.
    Partida: DEBITO wallet_usuario → CREDITO casa
    """
    if _transaccion_ya_procesada(id_transaccion):
        return

    # Bloqueo pesimista para evitar doble gasto
    EntradaContable.objects.select_for_update().filter(usuario=usuario)

    saldo_actual = obtener_saldo(usuario)
    if saldo_actual < monto:
        raise SaldoInsuficienteError(
            f"Saldo insuficiente. Disponible: {saldo_actual}, solicitado: {monto}."
        )

    _crear_par_contable(
        cuenta_debito=TipoCuenta.WALLET_USUARIO,
        cuenta_credito=TipoCuenta.CASA,
        usuario_debito=usuario,
        usuario_credito=None,
        monto=monto,
        id_transaccion=id_transaccion,
        tipo_referencia=TipoReferencia.RETIRO,
    )


@transaction.atomic
def bloquear_fondos_apuesta(
    usuario,
    monto: Decimal,
    *,
    id_transaccion: uuid.UUID,
    referencia_id: uuid.UUID = None,
) -> None:
    """
    Mueve fondos de wallet_usuario a apuestas_pendientes al confirmar una apuesta.
    Partida: DEBITO wallet_usuario → CREDITO apuestas_pendientes
    """
    if _transaccion_ya_procesada(id_transaccion):
        return

    EntradaContable.objects.select_for_update().filter(usuario=usuario)

    saldo_actual = obtener_saldo(usuario)
    if saldo_actual < monto:
        raise SaldoInsuficienteError(
            f"Saldo insuficiente para apostar. Disponible: {saldo_actual}."
        )

    _crear_par_contable(
        cuenta_debito=TipoCuenta.WALLET_USUARIO,
        cuenta_credito=TipoCuenta.APUESTAS_PENDIENTES,
        usuario_debito=usuario,
        usuario_credito=usuario,
        monto=monto,
        id_transaccion=id_transaccion,
        tipo_referencia=TipoReferencia.APUESTA,
        referencia_id=referencia_id,
    )


@transaction.atomic
def liberar_fondos_ganancia(
    usuario,
    stake: Decimal,
    odds: Decimal,
    *,
    id_apuesta: uuid.UUID,
) -> None:
    """
    Liquida una apuesta ganadora.
    payout = stake × odds (precisión exacta con Decimal)
    Partidas:
      DEBITO apuestas_pendientes → CREDITO wallet_usuario (stake)
      DEBITO casa → CREDITO wallet_usuario (ganancia)
    """
    id_tx_devolucion = uuid.uuid5(id_apuesta, "devolucion_stake")
    id_tx_ganancia = uuid.uuid5(id_apuesta, "ganancia")

    payout_total = stake * odds
    ganancia = payout_total - stake  # solo la ganancia neta

    if not _transaccion_ya_procesada(id_tx_devolucion):
        EntradaContable.objects.select_for_update().filter(usuario=usuario)
        # Devolver stake desde apuestas_pendientes
        _crear_par_contable(
            cuenta_debito=TipoCuenta.APUESTAS_PENDIENTES,
            cuenta_credito=TipoCuenta.WALLET_USUARIO,
            usuario_debito=usuario,
            usuario_credito=usuario,
            monto=stake,
            id_transaccion=id_tx_devolucion,
            tipo_referencia=TipoReferencia.PAGO_GANANCIA,
            referencia_id=id_apuesta,
        )

    if not _transaccion_ya_procesada(id_tx_ganancia) and ganancia > Decimal("0"):
        # Acreditar ganancia desde la casa
        _crear_par_contable(
            cuenta_debito=TipoCuenta.CASA,
            cuenta_credito=TipoCuenta.WALLET_USUARIO,
            usuario_debito=None,
            usuario_credito=usuario,
            monto=ganancia,
            id_transaccion=id_tx_ganancia,
            tipo_referencia=TipoReferencia.PAGO_GANANCIA,
            referencia_id=id_apuesta,
        )


@transaction.atomic
def liberar_fondos_perdida(
    usuario,
    stake: Decimal,
    *,
    id_apuesta: uuid.UUID,
) -> None:
    """
    Liquida una apuesta perdida.
    Partida: DEBITO apuestas_pendientes → CREDITO casa
    """
    id_tx = uuid.uuid5(id_apuesta, "perdida")
    if _transaccion_ya_procesada(id_tx):
        return

    EntradaContable.objects.select_for_update().filter(usuario=usuario)

    _crear_par_contable(
        cuenta_debito=TipoCuenta.APUESTAS_PENDIENTES,
        cuenta_credito=TipoCuenta.CASA,
        usuario_debito=usuario,
        usuario_credito=None,
        monto=stake,
        id_transaccion=id_tx,
        tipo_referencia=TipoReferencia.PERDIDA,
        referencia_id=id_apuesta,
    )


@transaction.atomic
def devolver_apuesta_anulada(
    usuario,
    stake: Decimal,
    *,
    id_apuesta: uuid.UUID,
) -> None:
    """
    Devuelve el stake cuando un evento es anulado.
    Partida: DEBITO apuestas_pendientes → CREDITO wallet_usuario
    """
    id_tx = uuid.uuid5(id_apuesta, "devolucion_anulacion")
    if _transaccion_ya_procesada(id_tx):
        return

    EntradaContable.objects.select_for_update().filter(usuario=usuario)

    _crear_par_contable(
        cuenta_debito=TipoCuenta.APUESTAS_PENDIENTES,
        cuenta_credito=TipoCuenta.WALLET_USUARIO,
        usuario_debito=usuario,
        usuario_credito=usuario,
        monto=stake,
        id_transaccion=id_tx,
        tipo_referencia=TipoReferencia.DEVOLUCION,
        referencia_id=id_apuesta,
    )