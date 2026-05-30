"""
Property-based tests con Hypothesis para invariantes financieras del wallet.
"""
from decimal import Decimal
import uuid

from hypothesis import given, settings as hyp_settings, assume
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisDjangoTestCase

from test_support import crear_usuario_verificado, fundir_wallet
from wallet.services import (
    bloquear_fondos_apuesta,
    liberar_fondos_ganancia,
    obtener_saldo,
    quantizar_monto,
    retirar_fichas,
    verificar_balance_transaccion,
)
from wallet.exceptions import SaldoInsuficienteError


def decimal_financiero(min_value="1.0000", max_value="9999.0000"):
    return st.decimals(
        min_value=Decimal(min_value),
        max_value=Decimal(max_value),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    )


class TestInvariantesHypothesis(HypothesisDjangoTestCase):

    @given(monto=decimal_financiero())
    @hyp_settings(max_examples=30, deadline=5000)
    def test_recarga_siempre_balancea(self, monto):
        usuario = crear_usuario_verificado()
        id_tx = uuid.uuid4()
        monto = min(monto, Decimal("500.0000"))
        assume(monto >= Decimal("1.0000"))
        fundir_wallet(usuario, monto, id_transaccion=id_tx)
        self.assertTrue(verificar_balance_transaccion(id_tx))

    @given(
        recarga=decimal_financiero(max_value="500.0000"),
        retiro=decimal_financiero(max_value="499.0000"),
    )
    @hyp_settings(max_examples=30, deadline=5000)
    def test_saldo_nunca_negativo(self, recarga, retiro):
        assume(retiro <= recarga)
        usuario = crear_usuario_verificado()
        fundir_wallet(usuario, recarga)
        try:
            retirar_fichas(usuario, retiro, id_transaccion=uuid.uuid4())
        except SaldoInsuficienteError:
            pass
        self.assertGreaterEqual(obtener_saldo(usuario), Decimal("0"))

    @given(
        stake=decimal_financiero(max_value="500.0000"),
        odds=decimal_financiero(min_value="1.0100", max_value="50.0000"),
    )
    @hyp_settings(max_examples=30, deadline=5000)
    def test_payout_exacto_stake_por_odds(self, stake, odds):
        assume(stake >= Decimal("1.0000"))
        usuario = crear_usuario_verificado()
        recarga = min(stake + Decimal("10.0000"), Decimal("500.0000"))
        assume(recarga >= stake)
        fundir_wallet(usuario, recarga)

        id_apuesta = uuid.uuid4()
        bloquear_fondos_apuesta(
            usuario, stake,
            id_transaccion=uuid.uuid5(id_apuesta, "bloqueo"),
        )
        saldo_antes = obtener_saldo(usuario)
        liberar_fondos_ganancia(usuario, stake, odds, id_apuesta=id_apuesta)
        saldo_despues = obtener_saldo(usuario)

        payout_esperado = quantizar_monto(stake * odds)
        self.assertEqual(saldo_despues - saldo_antes, payout_esperado)
