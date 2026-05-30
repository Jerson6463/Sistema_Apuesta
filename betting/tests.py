"""
Tests de la máquina de estados de Apuesta, validaciones de negocio y liquidación.
TDD: escritos antes de los modelos y servicios de betting.
"""
from datetime import date
from decimal import Decimal
import uuid

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from users.models import Usuario
from wallet.services import recargar_fichas, obtener_saldo

from betting.models import (
    Evento, EstadoEvento,
    Mercado, TipoMercado, EstadoMercado,
    Cuota,
    Apuesta, EstadoApuesta,
)
from betting.services import (
    crear_apuesta,
    liquidar_apuesta,
    anular_apuesta,
)
from betting.exceptions import (
    EventoNoDisponibleError,
    UsuarioNoHabilitadoError,
    SaldoInsuficienteApuestaError,
    MontoFueraDeRangoError,
    MercadoCerradoError,
    ApuestaYaLiquidadaError,
)


def crear_usuario_verificado(username="kelly_bet"):
    return Usuario.objects.create_user(
        username=username,
        email=f"{username}@test.com",
        password="pass1234",
        dni="12345678",
        fecha_nacimiento=date(1995, 6, 15),
        estado="verificado",
    )


def crear_evento_programado():
    return Evento.objects.create(
        nombre="Peru vs Brasil - Mundial 2026",
        deporte="futbol",
        equipo_local="Peru",
        equipo_visitante="Brasil",
        fecha_inicio=timezone.now() + timezone.timedelta(hours=2),
        estado=EstadoEvento.PROGRAMADO,
    )


def crear_mercado_y_cuotas(evento):
    mercado = Mercado.objects.create(
        evento=evento,
        tipo=TipoMercado.UNO_X_DOS,
        estado=EstadoMercado.ABIERTO,
        monto_minimo=Decimal("1.0000"),
        monto_maximo=Decimal("1000.0000"),
    )
    cuota_local = Cuota.objects.create(
        mercado=mercado,
        seleccion="local",
        valor=Decimal("2.5000"),
        activa=True,
    )
    Cuota.objects.create(mercado=mercado, seleccion="empate", valor=Decimal("3.0000"), activa=True)
    Cuota.objects.create(mercado=mercado, seleccion="visitante", valor=Decimal("2.8000"), activa=True)
    return mercado, cuota_local


class EstadoEventoTest(TestCase):
    def test_evento_inicia_programado(self):
        evento = crear_evento_programado()
        self.assertEqual(evento.estado, EstadoEvento.PROGRAMADO)

    def test_transicion_programado_a_en_vivo(self):
        evento = crear_evento_programado()
        evento.iniciar()
        self.assertEqual(evento.estado, EstadoEvento.EN_VIVO)

    def test_transicion_en_vivo_a_finalizado(self):
        evento = crear_evento_programado()
        evento.iniciar()
        evento.finalizar()
        self.assertEqual(evento.estado, EstadoEvento.FINALIZADO)

    def test_no_puede_ir_de_finalizado_a_programado(self):
        evento = crear_evento_programado()
        evento.iniciar()
        evento.finalizar()
        with self.assertRaises(Exception):
            evento.iniciar()

    def test_suspension_desde_en_vivo(self):
        evento = crear_evento_programado()
        evento.iniciar()
        evento.suspender()
        self.assertEqual(evento.estado, EstadoEvento.SUSPENDIDO)

    def test_anulacion_desde_programado(self):
        evento = crear_evento_programado()
        evento.anular()
        self.assertEqual(evento.estado, EstadoEvento.ANULADO)


class CrearApuestaValidacionesTest(TestCase):
    def setUp(self):
        self.usuario = crear_usuario_verificado()
        recargar_fichas(self.usuario, Decimal("500.0000"), id_transaccion=uuid.uuid4())
        self.evento = crear_evento_programado()
        self.mercado, self.cuota = crear_mercado_y_cuotas(self.evento)

    def test_apuesta_exitosa_crea_registro(self):
        apuesta = crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("50.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        self.assertEqual(apuesta.estado, EstadoApuesta.ACEPTADA)

    def test_apuesta_bloquea_fondos_en_wallet(self):
        saldo_antes = obtener_saldo(self.usuario)
        crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("100.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        saldo_despues = obtener_saldo(self.usuario)
        self.assertEqual(saldo_antes - saldo_despues, Decimal("100.0000"))

    def test_usuario_no_verificado_no_puede_apostar(self):
        usuario_no_verificado = crear_usuario_verificado("kelly_noverif")
        usuario_no_verificado.estado = "pendiente_verificacion"
        usuario_no_verificado.save()
        with self.assertRaises(UsuarioNoHabilitadoError):
            crear_apuesta(
                usuario=usuario_no_verificado,
                cuota=self.cuota,
                monto=Decimal("10.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_usuario_autoexcluido_no_puede_apostar(self):
        self.usuario.estado = "autoexcluido"
        self.usuario.save()
        with self.assertRaises(UsuarioNoHabilitadoError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("10.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_saldo_insuficiente_lanza_error(self):
        with self.assertRaises(SaldoInsuficienteApuestaError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("9999.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_monto_menor_minimo_lanza_error(self):
        with self.assertRaises(MontoFueraDeRangoError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("0.5000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_monto_mayor_maximo_lanza_error(self):
        recargar_fichas(self.usuario, Decimal("5000.0000"), id_transaccion=uuid.uuid4())
        with self.assertRaises(MontoFueraDeRangoError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("9999.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_evento_en_vivo_no_acepta_apuesta_simple(self):
        self.evento.iniciar()
        with self.assertRaises(EventoNoDisponibleError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("10.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_mercado_cerrado_no_acepta_apuesta(self):
        self.mercado.estado = EstadoMercado.CERRADO
        self.mercado.save()
        with self.assertRaises(MercadoCerradoError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("10.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_apuesta_idempotente(self):
        clave = uuid.uuid4()
        apuesta1 = crear_apuesta(
            usuario=self.usuario, cuota=self.cuota,
            monto=Decimal("50.0000"), clave_idempotencia=clave,
        )
        apuesta2 = crear_apuesta(
            usuario=self.usuario, cuota=self.cuota,
            monto=Decimal("50.0000"), clave_idempotencia=clave,
        )
        self.assertEqual(apuesta1.id, apuesta2.id)


class LiquidacionApuestaTest(TestCase):
    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_liq")
        recargar_fichas(self.usuario, Decimal("1000.0000"), id_transaccion=uuid.uuid4())
        self.evento = crear_evento_programado()
        self.mercado, self.cuota = crear_mercado_y_cuotas(self.evento)
        self.apuesta = crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("100.0000"),
            clave_idempotencia=uuid.uuid4(),
        )

    def test_liquidacion_ganadora_acredita_payout(self):
        saldo_antes = obtener_saldo(self.usuario)
        self.evento.iniciar()
        self.evento.finalizar()
        liquidar_apuesta(self.apuesta, resultado_ganador="local")
        saldo_despues = obtener_saldo(self.usuario)
        payout_esperado = Decimal("100.0000") * Decimal("2.5000")
        self.assertEqual(saldo_despues - saldo_antes, payout_esperado)
        self.apuesta.refresh_from_db()
        self.assertEqual(self.apuesta.estado, EstadoApuesta.GANADA)

    def test_liquidacion_perdedora_libera_fondos_a_casa(self):
        saldo_antes = obtener_saldo(self.usuario)
        self.evento.iniciar()
        self.evento.finalizar()
        liquidar_apuesta(self.apuesta, resultado_ganador="visitante")
        saldo_despues = obtener_saldo(self.usuario)
        self.assertEqual(saldo_despues, saldo_antes)
        self.apuesta.refresh_from_db()
        self.assertEqual(self.apuesta.estado, EstadoApuesta.PERDIDA)

    def test_no_se_puede_liquidar_dos_veces(self):
        self.evento.iniciar()
        self.evento.finalizar()
        liquidar_apuesta(self.apuesta, resultado_ganador="local")
        with self.assertRaises(ApuestaYaLiquidadaError):
            liquidar_apuesta(self.apuesta, resultado_ganador="local")

    def test_anulacion_devuelve_stake(self):
        saldo_antes = obtener_saldo(self.usuario)
        anular_apuesta(self.apuesta)
        saldo_despues = obtener_saldo(self.usuario)
        self.assertEqual(saldo_despues - saldo_antes, Decimal("100.0000"))
        self.apuesta.refresh_from_db()
        self.assertEqual(self.apuesta.estado, EstadoApuesta.ANULADA)


class PagoCalculadoTest(TestCase):
    """El pago potencial se calcula como stake × odds al crear la apuesta."""

    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_pago")
        recargar_fichas(self.usuario, Decimal("500.0000"), id_transaccion=uuid.uuid4())
        evento = crear_evento_programado()
        mercado, self.cuota = crear_mercado_y_cuotas(evento)

    def test_pago_potencial_es_stake_por_odds(self):
        apuesta = crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("100.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        self.assertEqual(
            apuesta.pago_potencial,
            Decimal("100.0000") * Decimal("2.5000"),
        )

    def test_cuota_snapshot_se_guarda_al_apostar(self):
        valor_original = self.cuota.valor
        apuesta = crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("50.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        # Simular cambio de cuota posterior
        self.cuota.valor = Decimal("9.9999")
        self.cuota.save()
        apuesta.refresh_from_db()
        self.assertEqual(apuesta.cuota_al_apostar, valor_original)


class ApuestaCombinada_Test(TestCase):
    """Tests de apuesta combinada: cuota total, selecciones excluyentes y liquidación."""

    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_comb")
        recargar_fichas(self.usuario, Decimal("500.0000"), id_transaccion=uuid.uuid4())
        self.evento = crear_evento_programado()
        self.mercado, self.cuota_local = crear_mercado_y_cuotas(self.evento)

    def test_selecciones_mismo_mercado_lanza_error(self):
        from betting.services import crear_apuesta_combinada
        from betting.exceptions import SeleccionMutuamenteExcluyenteError
        from betting.models import Cuota

        cuota_visitante = Cuota.objects.get(mercado=self.mercado, seleccion="visitante")
        with self.assertRaises(SeleccionMutuamenteExcluyenteError):
            crear_apuesta_combinada(
                usuario=self.usuario,
                cuotas=[self.cuota_local, cuota_visitante],
                monto=Decimal("50.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_cuota_total_es_producto_de_cuotas_individuales(self):
        from betting.services import crear_apuesta_combinada
        from betting.models import Cuota, Mercado, EstadoMercado

        evento2 = crear_evento_programado()
        evento2.nombre = "Otro Partido Test"
        evento2.save()
        mercado2 = Mercado.objects.create(
            evento=evento2, tipo="1X2", estado=EstadoMercado.ABIERTO,
            monto_minimo=Decimal("1.0000"), monto_maximo=Decimal("1000.0000"),
        )
        cuota2 = Cuota.objects.create(mercado=mercado2, seleccion="local", valor=Decimal("2.0000"), activa=True)

        combinada = crear_apuesta_combinada(
            usuario=self.usuario,
            cuotas=[self.cuota_local, cuota2],
            monto=Decimal("50.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        cuota_esperada = self.cuota_local.valor * cuota2.valor
        self.assertEqual(combinada.cuota_total, cuota_esperada)


class CashOutTest(TestCase):
    """Tests del cash-out: fórmula exacta y validación de estado."""

    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_cashout")
        recargar_fichas(self.usuario, Decimal("500.0000"), id_transaccion=uuid.uuid4())
        self.evento = crear_evento_programado()
        self.mercado, self.cuota = crear_mercado_y_cuotas(self.evento)
        self.apuesta = crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("100.0000"),
            clave_idempotencia=uuid.uuid4(),
        )

    def test_formula_cash_out_correcta(self):
        from betting.services import hacer_cash_out
        from wallet.services import obtener_saldo

        odds_original = self.apuesta.cuota_al_apostar
        odds_actual = self.cuota.valor  # mismo valor (no cambió en el test)
        factor = Decimal("0.9000")
        monto_esperado = (
            Decimal("100.0000") * odds_original / odds_actual * factor
        ).quantize(Decimal("0.0001"))

        monto_recibido = hacer_cash_out(self.apuesta, factor_casa=factor)
        self.assertEqual(monto_recibido, monto_esperado)

    def test_cash_out_cambia_estado_a_cash_out(self):
        from betting.services import hacer_cash_out
        from betting.models import EstadoApuesta
        hacer_cash_out(self.apuesta, factor_casa=Decimal("0.9000"))
        self.apuesta.refresh_from_db()
        self.assertEqual(self.apuesta.estado, EstadoApuesta.CASH_OUT)

    def test_cash_out_sobre_apuesta_liquidada_lanza_error(self):
        from betting.services import hacer_cash_out
        from betting.exceptions import CashOutNoDisponibleError
        self.evento.iniciar()
        self.evento.finalizar()
        from betting.services import liquidar_apuesta
        liquidar_apuesta(self.apuesta, resultado_ganador="local")
        with self.assertRaises(CashOutNoDisponibleError):
            hacer_cash_out(self.apuesta)