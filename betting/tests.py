"""
Tests de la máquina de estados de Apuesta, validaciones de negocio y liquidación.
TDD: escritos antes de los modelos y servicios de betting.
"""
from decimal import Decimal
import uuid

from django.test import TestCase
from django.utils import timezone

from test_support import crear_usuario_verificado, fundir_wallet
from wallet.services import retirar_fichas, obtener_saldo, recargar_fichas, quantizar_monto

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


def _estado_apuesta(apuesta) -> str:
    """Lee estado sin refresh_from_db() (FSMField protected=True)."""
    return Apuesta.objects.values_list("estado", flat=True).get(pk=apuesta.pk)


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
        fundir_wallet(self.usuario, Decimal("500.0000"))
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
        self.mercado.monto_maximo = Decimal("5000.0000")
        self.mercado.save(update_fields=["monto_maximo"])
        # Saldo 100, apuesta 200 → falla wallet, no límite de mercado (max 5000).
        retirar_fichas(self.usuario, Decimal("400.0000"), id_transaccion=uuid.uuid4())
        with self.assertRaises(SaldoInsuficienteApuestaError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("200.0000"),
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

    def test_evento_programado_pasado_inicio_no_acepta_prematch(self):
        from freezegun import freeze_time

        inicio = timezone.now() + timezone.timedelta(hours=1)
        self.evento.fecha_inicio = inicio
        self.evento.save(update_fields=["fecha_inicio"])

        with freeze_time(inicio + timezone.timedelta(minutes=5)):
            with self.assertRaises(EventoNoDisponibleError):
                crear_apuesta(
                    usuario=self.usuario,
                    cuota=self.cuota,
                    monto=Decimal("10.0000"),
                    clave_idempotencia=uuid.uuid4(),
                )

    def test_margen_seguridad_un_minuto_antes_del_inicio(self):
        from freezegun import freeze_time

        inicio = timezone.now() + timezone.timedelta(hours=2)
        self.evento.fecha_inicio = inicio
        self.evento.save(update_fields=["fecha_inicio"])

        with freeze_time(inicio - timezone.timedelta(seconds=30)):
            with self.assertRaises(EventoNoDisponibleError):
                crear_apuesta(
                    usuario=self.usuario,
                    cuota=self.cuota,
                    monto=Decimal("10.0000"),
                    clave_idempotencia=uuid.uuid4(),
                )

    def test_prematch_valido_dos_horas_antes_del_inicio(self):
        from freezegun import freeze_time

        inicio = timezone.now() + timezone.timedelta(hours=2)
        self.evento.fecha_inicio = inicio
        self.evento.save(update_fields=["fecha_inicio"])

        with freeze_time(inicio - timezone.timedelta(hours=1)):
            apuesta = crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("10.0000"),
                clave_idempotencia=uuid.uuid4(),
            )
            self.assertEqual(apuesta.estado, EstadoApuesta.ACEPTADA)

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
        fundir_wallet(self.usuario, Decimal("1000.0000"))
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
        self.assertEqual(_estado_apuesta(self.apuesta), EstadoApuesta.GANADA)

    def test_liquidacion_perdedora_libera_fondos_a_casa(self):
        saldo_antes = obtener_saldo(self.usuario)
        self.evento.iniciar()
        self.evento.finalizar()
        liquidar_apuesta(self.apuesta, resultado_ganador="visitante")
        saldo_despues = obtener_saldo(self.usuario)
        self.assertEqual(saldo_despues, saldo_antes)
        self.assertEqual(_estado_apuesta(self.apuesta), EstadoApuesta.PERDIDA)

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
        self.assertEqual(_estado_apuesta(self.apuesta), EstadoApuesta.ANULADA)


class PagoCalculadoTest(TestCase):
    """El pago potencial se calcula como stake × odds al crear la apuesta."""

    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_pago")
        fundir_wallet(self.usuario, Decimal("500.0000"))
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
        # FSM protected=True: no refresh_from_db() sobre `estado`.
        apuesta.refresh_from_db(fields=["cuota_al_apostar", "monto_apostado", "pago_potencial"])
        self.assertEqual(apuesta.cuota_al_apostar, valor_original)


class ApuestaCombinada_Test(TestCase):
    """Tests de apuesta combinada: cuota total, selecciones excluyentes y liquidación."""

    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_comb")
        fundir_wallet(self.usuario, Decimal("500.0000"))
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
        fundir_wallet(self.usuario, Decimal("500.0000"))
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

        # No usar refresh_from_db() sin excluir `estado`: FSMField protected=True
        # dispara error al reasignar el estado desde la DB. Releer la instancia.
        apuesta_db = Apuesta.objects.get(pk=self.apuesta.pk)
        self.assertEqual(apuesta_db.estado, EstadoApuesta.CASH_OUT)

    def test_cash_out_refresh_parcial_sin_estado(self):
        """Bypass seguro: refresh excluyendo el campo FSM protegido."""
        from betting.services import hacer_cash_out
        from betting.models import EstadoApuesta

        hacer_cash_out(self.apuesta, factor_casa=Decimal("0.9000"))
        self.apuesta.refresh_from_db(fields=["monto_apostado", "cuota_al_apostar", "pago_potencial"])
        self.assertEqual(
            Apuesta.objects.values_list("estado", flat=True).get(pk=self.apuesta.pk),
            EstadoApuesta.CASH_OUT,
        )

    def test_cash_out_sobre_apuesta_liquidada_lanza_error(self):
        from betting.services import hacer_cash_out
        from betting.exceptions import CashOutNoDisponibleError
        self.evento.iniciar()
        self.evento.finalizar()
        from betting.services import liquidar_apuesta
        liquidar_apuesta(self.apuesta, resultado_ganador="local")
        with self.assertRaises(CashOutNoDisponibleError):
            hacer_cash_out(self.apuesta)

    def test_cash_out_cuota_invalida_lanza_error(self):
        from betting.services import hacer_cash_out
        from betting.exceptions import CashOutNoDisponibleError

        self.cuota.valor = Decimal("0.0000")
        self.cuota.save(update_fields=["valor"])
        with self.assertRaises(CashOutNoDisponibleError):
            hacer_cash_out(self.apuesta)

    def test_cash_out_con_ganancia_acredita_diferencia(self):
        from betting.services import hacer_cash_out
        from wallet.models import EntradaContable, TipoReferencia

        self.cuota.valor = Decimal("3.0000")
        self.cuota.save(update_fields=["valor"])
        apuesta_alta = crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("100.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        self.cuota.valor = Decimal("1.5000")
        self.cuota.save(update_fields=["valor"])

        monto = hacer_cash_out(apuesta_alta, factor_casa=Decimal("0.9000"))
        self.assertGreater(monto, Decimal("100.0000"))
        self.assertTrue(
            EntradaContable.objects.filter(
                tipo_referencia=TipoReferencia.CASH_OUT,
                referencia_id=apuesta_alta.id,
            ).exists()
        )


class ValidacionesExtraServicesTest(TestCase):
    """Cubre ramas de validación aún no ejercitadas en services.py."""

    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_extra")
        fundir_wallet(self.usuario, Decimal("500.0000"))
        self.evento = crear_evento_programado()
        self.mercado, self.cuota = crear_mercado_y_cuotas(self.evento)

    def test_mercado_suspendido_rechaza_apuesta(self):
        self.mercado.estado = EstadoMercado.SUSPENDIDO
        self.mercado.save(update_fields=["estado"])
        with self.assertRaises(MercadoCerradoError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("10.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_evento_finalizado_rechaza_prematch(self):
        self.evento.iniciar()
        self.evento.finalizar()
        with self.assertRaises(EventoNoDisponibleError):
            crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("10.0000"),
                clave_idempotencia=uuid.uuid4(),
            )

    def test_a_utc_normaliza_datetime_naive(self):
        from datetime import datetime
        from betting.services import _a_utc

        naive = datetime(2026, 6, 15, 18, 0, 0)
        normalizado = _a_utc(naive)
        self.assertIsNotNone(normalizado.tzinfo)

    def test_anular_apuesta_ya_liquidada_lanza_error(self):
        apuesta = crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("50.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        self.evento.iniciar()
        self.evento.finalizar()
        liquidar_apuesta(apuesta, resultado_ganador="local")
        with self.assertRaises(ApuestaYaLiquidadaError):
            anular_apuesta(apuesta)


class RegistrarCambioCuotaTest(TestCase):
    def setUp(self):
        self.evento = crear_evento_programado()
        self.mercado, self.cuota = crear_mercado_y_cuotas(self.evento)

    def test_registrar_cambio_cuota_crea_historial_y_publica(self):
        from unittest.mock import patch
        from betting.models import HistorialCuota
        from betting.services import registrar_cambio_cuota

        nuevo = Decimal("2.7500")
        with patch("betting.tasks.publicar_actualizacion_cuota.delay") as mock_delay:
            registrar_cambio_cuota(self.cuota, nuevo)

        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.valor, nuevo)
        historial = HistorialCuota.objects.get(cuota=self.cuota)
        self.assertEqual(historial.valor_anterior, Decimal("2.5000"))
        self.assertEqual(historial.valor_nuevo, nuevo)
        mock_delay.assert_called_once()


class ModelosRepresentacionTest(TestCase):
    """__str__, reanudar evento y FSM de ApuestaCombinada."""

    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_repr")
        self.evento = crear_evento_programado()
        self.mercado, self.cuota = crear_mercado_y_cuotas(self.evento)

    def test_evento_reanudar_desde_suspendido(self):
        self.evento.iniciar()
        self.evento.suspender()
        self.evento.reanudar()
        self.assertEqual(self.evento.estado, EstadoEvento.EN_VIVO)

    def test_str_evento_mercado_cuota_apuesta(self):
        fundir_wallet(self.usuario, Decimal("100.0000"))
        apuesta = crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("10.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        self.assertIn("Peru vs Brasil", str(self.evento))
        self.assertIn("1X2", str(self.mercado))
        self.assertIn("local", str(self.cuota))
        self.assertIn(str(apuesta.id), str(apuesta))

    def test_combinada_str_y_transiciones_fsm(self):
        from betting.models import ApuestaCombinada
        from betting.services import crear_apuesta_combinada

        evento2 = crear_evento_programado()
        evento2.nombre = "Chile vs Argentina"
        evento2.save(update_fields=["nombre"])
        mercado2 = Mercado.objects.create(
            evento=evento2,
            tipo=TipoMercado.UNO_X_DOS,
            estado=EstadoMercado.ABIERTO,
            monto_minimo=Decimal("1.0000"),
            monto_maximo=Decimal("1000.0000"),
        )
        cuota2 = Cuota.objects.create(
            mercado=mercado2, seleccion="local", valor=Decimal("2.0000"), activa=True
        )
        fundir_wallet(self.usuario, Decimal("200.0000"))
        combinada = crear_apuesta_combinada(
            usuario=self.usuario,
            cuotas=[self.cuota, cuota2],
            monto=Decimal("50.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        self.assertIn("Combinada", str(combinada))

        combinada_db = ApuestaCombinada.objects.get(pk=combinada.pk)
        combinada_db.marcar_ganada()
        combinada_db.save()
        self.assertEqual(
            ApuestaCombinada.objects.values_list("estado", flat=True).get(pk=combinada.pk),
            EstadoApuesta.GANADA,
        )

        combinada2 = crear_apuesta_combinada(
            usuario=self.usuario,
            cuotas=[self.cuota, cuota2],
            monto=Decimal("30.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        combinada2_db = ApuestaCombinada.objects.get(pk=combinada2.pk)
        combinada2_db.marcar_perdida()
        combinada2_db.save()
        self.assertEqual(
            ApuestaCombinada.objects.values_list("estado", flat=True).get(pk=combinada2.pk),
            EstadoApuesta.PERDIDA,
        )

        combinada3 = crear_apuesta_combinada(
            usuario=self.usuario,
            cuotas=[self.cuota, cuota2],
            monto=Decimal("20.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        combinada3_db = ApuestaCombinada.objects.get(pk=combinada3.pk)
        combinada3_db.marcar_anulada()
        combinada3_db.save()
        self.assertEqual(
            ApuestaCombinada.objects.values_list("estado", flat=True).get(pk=combinada3.pk),
            EstadoApuesta.ANULADA,
        )


class SignalsAuditoriaTest(TestCase):
    def setUp(self):
        self.usuario = crear_usuario_verificado("kelly_sig")
        fundir_wallet(self.usuario, Decimal("500.0000"))
        self.evento = crear_evento_programado()
        self.mercado, self.cuota = crear_mercado_y_cuotas(self.evento)

    def test_signal_apuesta_registra_auditoria(self):
        from audit.models import RegistroAuditoria, TipoEventoAuditoria

        antes = RegistroAuditoria.objects.filter(tipo_evento=TipoEventoAuditoria.APUESTA).count()
        crear_apuesta(
            usuario=self.usuario,
            cuota=self.cuota,
            monto=Decimal("25.0000"),
            clave_idempotencia=uuid.uuid4(),
        )
        despues = RegistroAuditoria.objects.filter(tipo_evento=TipoEventoAuditoria.APUESTA).count()
        self.assertEqual(despues, antes + 1)

    def test_signal_historial_cuota_registra_auditoria(self):
        from audit.models import RegistroAuditoria, TipoEventoAuditoria
        from betting.models import HistorialCuota

        antes = RegistroAuditoria.objects.filter(tipo_evento=TipoEventoAuditoria.ODDS).count()
        HistorialCuota.objects.create(
            cuota=self.cuota,
            valor_anterior=Decimal("2.5000"),
            valor_nuevo=Decimal("2.6000"),
        )
        despues = RegistroAuditoria.objects.filter(tipo_evento=TipoEventoAuditoria.ODDS).count()
        self.assertEqual(despues, antes + 1)

    def test_signal_apuesta_tolerante_a_fallo_auditoria(self):
        from unittest.mock import patch

        with patch("audit.services.registrar_evento", side_effect=RuntimeError("audit down")):
            apuesta = crear_apuesta(
                usuario=self.usuario,
                cuota=self.cuota,
                monto=Decimal("15.0000"),
                clave_idempotencia=uuid.uuid4(),
            )
        self.assertIsNotNone(apuesta.id)

    def test_signal_historial_no_audita_si_no_es_creacion(self):
        from audit.models import RegistroAuditoria, TipoEventoAuditoria
        from betting.models import HistorialCuota

        registro = HistorialCuota.objects.create(
            cuota=self.cuota,
            valor_anterior=Decimal("2.5000"),
            valor_nuevo=Decimal("2.6000"),
        )
        despues_create = RegistroAuditoria.objects.filter(
            tipo_evento=TipoEventoAuditoria.ODDS
        ).count()
        registro.valor_nuevo = Decimal("2.7000")
        registro.save()
        despues_update = RegistroAuditoria.objects.filter(
            tipo_evento=TipoEventoAuditoria.ODDS
        ).count()
        self.assertEqual(despues_create, despues_update)

    def test_signal_historial_tolerante_a_fallo_auditoria(self):
        from unittest.mock import patch
        from betting.models import HistorialCuota

        with patch("audit.services.registrar_evento", side_effect=RuntimeError("audit down")):
            historial = HistorialCuota.objects.create(
                cuota=self.cuota,
                valor_anterior=Decimal("2.5000"),
                valor_nuevo=Decimal("2.6500"),
            )
        self.assertIsNotNone(historial.id)
