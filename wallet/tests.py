"""
Tests críticos del wallet con partida doble.
"""
from decimal import Decimal
import uuid

from django.test import TestCase, TransactionTestCase
from django.db import connection

from test_support import crear_usuario_verificado, fundir_wallet
from wallet.models import EntradaContable, TipoCuenta, DireccionMovimiento
from wallet.services import (
    retirar_fichas,
    bloquear_fondos_apuesta,
    liberar_fondos_ganancia,
    obtener_saldo,
    verificar_balance_transaccion,
    recargar_fichas,
)
from wallet.exceptions import SaldoInsuficienteError, LimiteSuperadoError


class InvariantePartidaDobleTest(TestCase):
    """Toda transacción debe tener suma de débitos y créditos = 0."""

    def test_recarga_balancea_debito_y_credito(self):
        usuario = crear_usuario_verificado()
        id_tx = uuid.uuid4()
        fundir_wallet(usuario, Decimal("200.0000"))
        self.assertTrue(verificar_balance_transaccion(id_tx))

    def test_retiro_balancea_debito_y_credito(self):
        usuario = crear_usuario_verificado()
        id_tx1 = uuid.uuid4()
        fundir_wallet(usuario, Decimal("500.0000"), id_transaccion=id_tx1)
        id_tx2 = uuid.uuid4()
        retirar_fichas(usuario, Decimal("200.0000"), id_transaccion=id_tx2)
        self.assertTrue(verificar_balance_transaccion(id_tx2))

    def test_bloqueo_apuesta_balancea(self):
        usuario = crear_usuario_verificado()
        fundir_wallet(usuario, Decimal("1000.0000"))
        id_tx = uuid.uuid4()
        bloquear_fondos_apuesta(usuario, Decimal("100.0000"), id_transaccion=id_tx)
        self.assertTrue(verificar_balance_transaccion(id_tx))

    def test_suma_global_todas_transacciones_es_cero(self):
        usuario = crear_usuario_verificado()
        fundir_wallet(usuario, Decimal("300.0000"))
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
        fundir_wallet(usuario, Decimal("500.0000"))
        self.assertEqual(obtener_saldo(usuario), Decimal("500.0000"))

    def test_saldo_tras_retiro(self):
        usuario = crear_usuario_verificado()
        fundir_wallet(usuario, Decimal("500.0000"))
        retirar_fichas(usuario, Decimal("200.0000"), id_transaccion=uuid.uuid4())
        self.assertEqual(obtener_saldo(usuario), Decimal("300.0000"))

    def test_saldo_nunca_negativo(self):
        usuario = crear_usuario_verificado()
        fundir_wallet(usuario, Decimal("100.0000"))
        with self.assertRaises(SaldoInsuficienteError):
            retirar_fichas(usuario, Decimal("200.0000"), id_transaccion=uuid.uuid4())
        self.assertGreaterEqual(obtener_saldo(usuario), Decimal("0"))

    def test_saldo_disponible_excluye_fondos_bloqueados(self):
        usuario = crear_usuario_verificado()
        fundir_wallet(usuario, Decimal("500.0000"))
        bloquear_fondos_apuesta(usuario, Decimal("200.0000"), id_transaccion=uuid.uuid4())
        # saldo disponible = 300, no 500
        self.assertEqual(obtener_saldo(usuario), Decimal("300.0000"))


class PayoutPrecisionTest(TestCase):
    """El payout de una apuesta ganadora = stake × odds con precisión exacta."""

    def test_payout_exacto_decimal(self):
        usuario = crear_usuario_verificado()
        fundir_wallet(usuario, Decimal("1000.0000"))
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
        fundir_wallet(usuario, Decimal("1000.0000"))
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


class ConcurrenciaDobleGastoTest(TransactionTestCase):
    """
    Simula N requests simultáneas contra la misma cuenta.
    TransactionTestCase confirma cada operación en DB real para que los hilos
    vean datos committed (TestCase envuelve todo en una transacción no visible
    a otros hilos → deadlock / transacciones abortadas).
    """

    def _lanzar_hilos(self, objetivos, repeticiones=1):
        import threading

        errores = []
        barrera = threading.Barrier(len(objetivos) * repeticiones)

        def ejecutar(func):
            def wrapper():
                connection.close()
                try:
                    barrera.wait(timeout=5)
                    func()
                except Exception as exc:
                    errores.append(exc)
                finally:
                    connection.close()

            return wrapper

        hilos = [
            threading.Thread(target=ejecutar(obj))
            for obj in objetivos
            for _ in range(repeticiones)
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=30)

        return errores

    def test_n_recargas_simultaneas_misma_id_transaccion_no_duplican(self):
        usuario = crear_usuario_verificado()
        id_tx = uuid.uuid4()

        self._lanzar_hilos([
            lambda: recargar_fichas(
                usuario, Decimal("100.0000"), id_transaccion=id_tx
            )
        ] * 5)

        saldo = obtener_saldo(usuario)
        self.assertEqual(saldo, Decimal("100.0000"))

    def test_retiro_concurrente_no_genera_saldo_negativo(self):
        usuario = crear_usuario_verificado()
        fundir_wallet(usuario, Decimal("100.0000"))

        errores = self._lanzar_hilos([
            lambda: retirar_fichas(
                usuario, Decimal("60.0000"), id_transaccion=uuid.uuid4()
            )
        ] * 3)

        saldo_final = obtener_saldo(usuario)
        self.assertGreaterEqual(saldo_final, Decimal("0"))
        exitos = 3 - len([
            e for e in errores if isinstance(e, SaldoInsuficienteError)
        ])
        self.assertLessEqual(exitos, 1)
