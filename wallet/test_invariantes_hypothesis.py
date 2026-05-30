"""
Property-based tests con Hypothesis para invariantes financieras del wallet.

Invariantes verificadas:
  1. La suma global de débitos y créditos siempre es cero.
  2. Ningún wallet termina con saldo negativo.
  3. El payout de una apuesta ganadora siempre es stake × odds con precisión exacta.
"""
from datetime import date
from decimal import Decimal
import uuid

import pytest
from hypothesis import given, settings as hyp_settings, assume
from hypothesis import strategies as st
from django.test import TestCase

from users.models import Usuario
from wallet.services import (
    bloquear_fondos_apuesta,
    liberar_fondos_ganancia,
    obtener_saldo,
    recargar_fichas,
    retirar_fichas,
    verificar_balance_transaccion,
)
from wallet.exceptions import SaldoInsuficienteError


def decimal_financiero(min_value="1.0000", max_value="9999.0000"):
    """Genera Decimals con 4 cifras decimales como usamos en el sistema."""
    return st.decimals(
        min_value=Decimal(min_value),
        max_value=Decimal(max_value),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    )


def crear_usuario_unico():
    nombre = f"hyp_{uuid.uuid4().hex[:8]}"
    return Usuario.objects.create_user(
        username=nombre,
        email=f"{nombre}@hyp.test",
        password="pass1234",
        dni="12345678",
        fecha_nacimiento=date(1995, 6, 15),
        estado="verificado",
    )


@pytest.mark.django_db
class TestInvariantesHypothesis(TestCase):

    @given(monto=decimal_financiero())
    @hyp_settings(max_examples=30, deadline=5000)
    def test_recarga_siempre_balancea(self, monto):
        """Invariante 1: toda recarga crea entradas balanceadas (suma neta = 0)."""
        usuario = crear_usuario_unico()
        id_tx = uuid.uuid4()
        # Ajustar monto al límite diario
        monto = min(monto, Decimal("500.0000"))
        assume(monto >= Decimal("1.0000"))
        recargar_fichas(usuario, monto, id_transaccion=id_tx)
        assert verificar_balance_transaccion(id_tx)

    @given(
        recarga=decimal_financiero(max_value="500.0000"),
        retiro=decimal_financiero(max_value="499.0000"),
    )
    @hyp_settings(max_examples=30, deadline=5000)
    def test_saldo_nunca_negativo(self, recarga, retiro):
        """Invariante 2: ningún wallet puede quedar en saldo negativo."""
        assume(retiro <= recarga)
        usuario = crear_usuario_unico()
        recargar_fichas(usuario, recarga, id_transaccion=uuid.uuid4())
        try:
            retirar_fichas(usuario, retiro, id_transaccion=uuid.uuid4())
        except SaldoInsuficienteError:
            pass
        assert obtener_saldo(usuario) >= Decimal("0")

    @given(
        stake=decimal_financiero(max_value="500.0000"),
        odds=decimal_financiero(min_value="1.0100", max_value="50.0000"),
    )
    @hyp_settings(max_examples=30, deadline=5000)
    def test_payout_exacto_stake_por_odds(self, stake, odds):
        """Invariante 3: payout ganador = stake × odds exacto en Decimal."""
        assume(stake >= Decimal("1.0000"))
        usuario = crear_usuario_unico()
        recarga = min(stake + Decimal("10.0000"), Decimal("500.0000"))
        assume(recarga >= stake)
        recargar_fichas(usuario, recarga, id_transaccion=uuid.uuid4())

        id_apuesta = uuid.uuid4()
        bloquear_fondos_apuesta(
            usuario, stake,
            id_transaccion=uuid.uuid5(id_apuesta, "bloqueo"),
        )
        saldo_antes = obtener_saldo(usuario)
        liberar_fondos_ganancia(usuario, stake, odds, id_apuesta=id_apuesta)
        saldo_despues = obtener_saldo(usuario)

        payout_esperado = stake * odds
        assert saldo_despues - saldo_antes == payout_esperado