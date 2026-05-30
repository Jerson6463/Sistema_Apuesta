from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError

from users.validators import validar_dni_peruano, validar_mayor_de_edad
from users.models import Usuario, LimiteJuego, AutoExclusion


class ValidadorDNITest(TestCase):
    def test_dni_valido_acepta_8_digitos(self):
        self.assertIsNone(validar_dni_peruano("12345678"))

    def test_dni_invalido_letras(self):
        with self.assertRaises(ValidationError):
            validar_dni_peruano("1234567A")

    def test_dni_invalido_longitud(self):
        with self.assertRaises(ValidationError):
            validar_dni_peruano("1234567")

    def test_dni_vacio(self):
        with self.assertRaises(ValidationError):
            validar_dni_peruano("")


class ValidadorMayorEdadTest(TestCase):
    def test_mayor_de_18_es_valido(self):
        fecha = date.today() - timedelta(days=365 * 18 + 1)
        self.assertIsNone(validar_mayor_de_edad(fecha))

    def test_exactamente_18_es_valido(self):
        fecha = date.today() - timedelta(days=365 * 18)
        self.assertIsNone(validar_mayor_de_edad(fecha))

    def test_menor_de_18_lanza_error(self):
        fecha = date.today() - timedelta(days=365 * 17)
        with self.assertRaises(ValidationError):
            validar_mayor_de_edad(fecha)

    def test_nacido_hoy_lanza_error(self):
        with self.assertRaises(ValidationError):
            validar_mayor_de_edad(date.today())


class UsuarioModelTest(TestCase):
    def _crear_usuario(self, **kwargs):
        defaults = {
            "username": "kelly_test",
            "email": "kelly@test.com",
            "password": "pass1234",
            "dni": "12345678",
            "fecha_nacimiento": date(1995, 6, 15),
        }
        defaults.update(kwargs)
        return Usuario.objects.create_user(**defaults)

    def test_estado_inicial_es_pendiente_verificacion(self):
        u = self._crear_usuario()
        self.assertEqual(u.estado, "pendiente_verificacion")

    def test_usuario_no_puede_apostar_sin_verificar(self):
        u = self._crear_usuario()
        self.assertFalse(u.puede_apostar())

    def test_usuario_verificado_puede_apostar(self):
        u = self._crear_usuario()
        u.estado = "verificado"
        u.save()
        self.assertTrue(u.puede_apostar())

    def test_usuario_bloqueado_no_puede_apostar(self):
        u = self._crear_usuario()
        u.estado = "bloqueado"
        u.save()
        self.assertFalse(u.puede_apostar())

    def test_usuario_autoexcluido_no_puede_apostar(self):
        u = self._crear_usuario()
        u.estado = "autoexcluido"
        u.save()
        self.assertFalse(u.puede_apostar())


class LimiteJuegoTest(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="kelly_limite",
            email="kelly_limite@test.com",
            password="pass1234",
            dni="12345678",
            fecha_nacimiento=date(1995, 6, 15),
        )

    def test_limites_por_defecto_creados_con_usuario(self):
        limite = LimiteJuego.objects.get(usuario=self.usuario)
        self.assertIsNotNone(limite)
        self.assertEqual(limite.limite_diario, Decimal("500.0000"))
        self.assertEqual(limite.limite_semanal, Decimal("2000.0000"))
        self.assertEqual(limite.limite_mensual, Decimal("5000.0000"))

    def test_bajar_limite_es_inmediato(self):
        limite = LimiteJuego.objects.get(usuario=self.usuario)
        limite.actualizar_limite("diario", Decimal("100.0000"))
        self.assertEqual(limite.limite_diario, Decimal("100.0000"))

    def test_subir_limite_requiere_cooldown(self):
        limite = LimiteJuego.objects.get(usuario=self.usuario)
        with self.assertRaises(ValidationError):
            limite.actualizar_limite("diario", Decimal("9999.0000"))


class AutoExclusionTest(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="kelly_excl",
            email="kelly_excl@test.com",
            password="pass1234",
            dni="12345678",
            fecha_nacimiento=date(1995, 6, 15),
            estado="verificado",
        )

    def test_autoexclusion_temporal_cambia_estado(self):
        AutoExclusion.objects.crear_exclusion(self.usuario, "temporal_30")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.estado, "autoexcluido")

    def test_autoexclusion_indefinida(self):
        AutoExclusion.objects.crear_exclusion(self.usuario, "indefinida")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.estado, "autoexcluido")

    def test_no_puede_revertir_antes_del_tiempo(self):
        excl = AutoExclusion.objects.crear_exclusion(self.usuario, "temporal_7")
        with self.assertRaises(ValidationError):
            excl.revocar()