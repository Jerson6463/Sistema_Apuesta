"""
Tests críticos del wallet con partida doble.
Invariantes verificadas:
  1. La suma global de débitos y créditos de una misma transacción es siempre cero.
  2. Ningún wallet termina con saldo negativo.
  3. El payout de una apuesta ganadora siempre es stake × odds con precisión exacta.
"""
from datetime import date
from decimal import Decimal
import uuid

from django.test import TestCase
from django.db import transaction

from users.models import Usuario
from wallet.models import EntradaContable, TipoCuenta, DireccionMovimiento
from wallet.services import (
    recargar_fichas,
    retirar_fichas,
    bloquear_fondos_apuesta,
    liberar_fondos_ganancia,
    liberar_fondos_perdida,
    obtener_saldo,
    verificar_balance_transaccion,
)
from wallet.exceptions import SaldoInsuficienteError, LimiteSuperadoError


def crear_usuario_verificado(username="kelly_wallet"):
    u = Usuario.objects.create_user(
        username=username,
        email=f"{username}@test.com",
        password="pass1234",
        dni="12345678",
        fecha_nacimiento=date(1995, 6, 15),
        estado="verificado",
    )
    return u


class InvariantePartidaDobleTest(TestCase):
    """Toda transacción debe tener suma de débitos y créditos = 0."""

    def test_recarga_balancea_debito_y_credito(self):
        usuario = crear_usuario_verificado()
        id_tx = uuid.uuid4()
        recargar_fichas(usuario, Decimal("200.0000"), id_transaccion=id_tx)
        self.assertTrue(verificar_balance_transaccion(id_tx))

    def test_retiro_balancea_debito_y_credito(self):
        usuario = crear_usuario_verificado()
        id_tx1 = uuid.uuid4()
        recargar_fichas(usuario, Decimal("500.0000"), id_transaccion=id_tx1)
        id_tx2 = uuid.uuid4()
        retirar_fichas(usuario, Decimal("200.0000"), id_transaccion=id_tx2)
        self.assertTrue(verificar_balance_transaccion(id_tx2))

    def test_bloqueo_apuesta_balancea(self):
        usuario = crear_usuario_verificado()
        recargar_fichas(usuario, Decimal("1000.0000"), id_transaccion=uuid.uuid4())
        id_tx = uuid.uuid4()
        bloquear_fondos_apuesta(usuario, Decimal("100.0000"), id_transaccion=id_tx)
        self.assertTrue(verificar_balance_transaccion(id_tx))

    def test_suma_global_todas_transacciones_es_cero(self):
        usuario = crear_usuario_verificado()
        recargar_fichas(usuario, Decimal("300.0000"), id_transaccion=uuid.uuid4())
        retirar_fichas(usuario, Decimal("100.0000"), id_transaccion=uuid.uuid4())
        bloquear_fondos_apuesta(usuario, Decimal("50.0000"), id_transaccion=uuid.uuid4())

        total_creditos = sum(
            e.monto for e in EntradaContable.objects.filter(
                direccion=DireccionMovimiento.CREDITO
            )
        )
        total_debitos = sum(
            e.monto for e in EntradaContable.objects.filter(
                direccion=DireccionMovimiento.DEBITO
            )
        )
        self.assertEqual(total_creditos, total_debitos)


class SaldoTest(TestCase):
    """El saldo debe calcularse siempre, nunca almacenarse."""

    def test_saldo_inicial_es_cero(self):
        usuario = crear_usuario_verificado()
        self.assertEqual(obtener_saldo(usuario), Decimal("0.0000"))

    def test_saldo_tras_recarga(self):
        usuario = crear_usuario_verificado()
        recargar_fichas(usuario, Decimal("500.0000"), id_transaccion=uuid.uuid4())
        self.assertEqual(obtener_saldo(usuario), Decimal("500.0000"))

    def test_saldo_tras_retiro(self):
        usuario = crear_usuario_verificado()
        recargar_fichas(usuario, Decimal("500.0000"), id_transaccion=uuid.uuid4())
        retirar_fichas(usuario, Decimal("200.0000"), id_transaccion=uuid.uuid4())
        self.assertEqual(obtener_saldo(usuario), Decimal("300.0000"))

    def test_saldo_nunca_negativo(self):
        usuario = crear_usuario_verificado()
        recargar_fichas(usuario, Decimal("100.0000"), id_transaccion=uuid.uuid4())
        with self.assertRaises(SaldoInsuficienteError):
            retirar_fichas(usuario, Decimal("200.0000"), id_transaccion=uuid.uuid4())
        self.assertGreaterEqual(obtener_saldo(usuario), Decimal("0"))

    def test_saldo_disponible_excluye_fondos_bloqueados(self):
        usuario = crear_usuario_verificado()
        recargar_fichas(usuario, Decimal("500.0000"), id_transaccion=uuid.uuid4())
        bloquear_fondos_apuesta(usuario, Decimal("200.0000"), id_transaccion=uuid.uuid4())
        # saldo disponible = 300, no 500
        self.assertEqual(obtener_saldo(usuario), Decimal("300.0000"))


class PayoutPrecisionTest(TestCase):
    """El payout de una apuesta ganadora = stake × odds con precisión exacta."""

    def test_payout_exacto_decimal(self):
        usuario = crear_usuario_verificado()
        recargar_fichas(usuario, Decimal("1000.0000"), id_transaccion=uuid.uuid4())
        stake = Decimal("100.0000")
        odds = Decimal("2.5000")
        id_apuesta = uuid.uuid4()
        id_bloqueo = uuid.uuid4()

        bloquear_fondos_apuesta(usuario, stake, id_transaccion=id_bloqueo)
        saldo_antes = obtener_saldo(usuario)
        liberar_fondos_ganancia(usuario, stake, odds, id_apuesta=id_apuesta)
        saldo_despues = obtener_saldo(usuario)

        ganancia_esperada = stake * odds
        self.assertEqual(saldo_despues - saldo_antes, ganancia_esperada)

    def test_payout_no_usa_float(self):
        usuario = crear_usuario_verificado()
        recargar_fichas(usuario, Decimal("1000.0000"), id_transaccion=uuid.uuid4())
        stake = Decimal("33.3333")
        odds = Decimal("3.0000")

        bloquear_fondos_apuesta(usuario, stake, id_transaccion=uuid.uuid4())
        liberar_fondos_ganancia(usuario, stake, odds, id_apuesta=uuid.uuid4())

        for entrada in EntradaContable.objects.all():
            self.assertIsInstance(entrada.monto, Decimal)


class IdempotenciaTest(TestCase):
    """Reenviar la misma clave de transacción no duplica el movimiento."""

    def test_recarga_idempotente(self):
        usuario = crear_usuario_verificado()
        id_tx = uuid.uuid4()
        recargar_fichas(usuario, Decimal("100.0000"), id_transaccion=id_tx)
        recargar_fichas(usuario, Decimal("100.0000"), id_transaccion=id_tx)
        self.assertEqual(obtener_saldo(usuario), Decimal("100.0000"))


class LimiteJuegoWalletTest(TestCase):
    """El wallet respeta los límites de juego del usuario."""

    def test_recarga_supera_limite_diario(self):
        usuario = crear_usuario_verificado()
        # límite diario por defecto es 500
        with self.assertRaises(LimiteSuperadoError):
            recargar_fichas(usuario, Decimal("9999.0000"), id_transaccion=uuid.uuid4())