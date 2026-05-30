from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.core.exceptions import ValidationError

from users.validators import (
    calcular_digito_verificador_dni,
    calcular_digito_verificador_dni_letra,
    es_dni_peruano_valido,
    validar_digito_verificador_dni,
    validar_dni_con_verificador,
    validar_dni_peruano,
    validar_mayor_de_edad,
)
from users.models import Usuario, LimiteJuego, AutoExclusion

# DNI de prueba con dígito verificador ORE válido (1234567 + verificador 5).
DNI_VALIDO = "12345675"


class ValidadorDNITest(TestCase):
    def test_dni_valido_acepta_digito_verificador_correcto(self):
        self.assertIsNone(validar_dni_peruano(DNI_VALIDO))

    def test_calcular_digito_verificador_numerico(self):
        self.assertEqual(calcular_digito_verificador_dni("17801146"), 0)

    def test_calcular_digito_verificador_letra(self):
        self.assertEqual(calcular_digito_verificador_dni_letra("17801146"), "D")

    def test_es_dni_peruano_valido_funcion_pura(self):
        """RENIEC: 17801146 + verificador 0 (numérico) o D (letra ORE)."""
        self.assertTrue(es_dni_peruano_valido("17801146", "0"))
        self.assertTrue(es_dni_peruano_valido("17801146", "D"))
        self.assertFalse(es_dni_peruano_valido("17801146", "9"))
        # RENIEC sobre 8 dígitos: verificador numérico correcto es 1, no 9.
        self.assertTrue(es_dni_peruano_valido("12345678", "1"))
        self.assertFalse(es_dni_peruano_valido("12345678", "9"))

    def test_validar_dni_nueve_caracteres(self):
        self.assertTrue(validar_digito_verificador_dni("178011460"))
        self.assertTrue(validar_digito_verificador_dni("17801146D"))

    def test_dni_invalido_digito_verificador(self):
        with self.assertRaises(ValidationError):
            validar_dni_con_verificador("12345678", "9")

    def test_dni_valido_con_verificador_separado(self):
        self.assertIsNone(validar_dni_con_verificador("12345678", "1"))
        self.assertIsNone(validar_dni_con_verificador("17801146", "D"))

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
        fecha = date.today() - relativedelta(years=18, days=1)
        self.assertIsNone(validar_mayor_de_edad(fecha))

    def test_exactamente_18_es_valido(self):
        fecha = date.today() - relativedelta(years=18)
        self.assertIsNone(validar_mayor_de_edad(fecha))

    def test_menor_de_18_lanza_error(self):
        fecha = date.today() - relativedelta(years=17)
        with self.assertRaises(ValidationError):
            validar_mayor_de_edad(fecha)

    def test_nacido_hoy_lanza_error(self):
        with self.assertRaises(ValidationError):
            validar_mayor_de_edad(date.today())

    def test_cumpleanos_bisiesto_exactamente_18(self):
        """29-feb → edad exacta sin depender de 365 días fijos."""
        hoy = date.today()
        if hoy.month == 2 and hoy.day == 29:
            fecha = hoy.replace(year=hoy.year - 18)
        else:
            try:
                fecha = date(hoy.year - 18, 2, 29)
            except ValueError:
                self.skipTest("No aplica fuera de contexto bisiesto")
        self.assertIsNone(validar_mayor_de_edad(fecha))


class UsuarioModelTest(TestCase):
    def _crear_usuario(self, **kwargs):
        defaults = {
            "username": "kelly_test",
            "email": "kelly@test.com",
            "password": "pass1234",
            "dni": DNI_VALIDO,
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

    def test_usuario_pendiente_no_puede_iniciar_sesion(self):
        u = self._crear_usuario()
        self.assertFalse(u.puede_iniciar_sesion())
        self.assertIn("pendiente", u.mensaje_bloqueo_sesion().lower())

    def test_usuario_verificado_puede_iniciar_sesion(self):
        u = self._crear_usuario()
        u.estado = "verificado"
        u.save()
        self.assertTrue(u.puede_iniciar_sesion())

    def test_staff_puede_iniciar_sesion_sin_verificar(self):
        u = self._crear_usuario()
        u.is_staff = True
        u.save()
        self.assertTrue(u.puede_iniciar_sesion())

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
            dni=DNI_VALIDO,
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
        from freezegun import freeze_time

        limite = LimiteJuego.objects.get(usuario=self.usuario)
        valor_original = limite.limite_diario
        nuevo_valor = Decimal("9999.0000")

        with freeze_time("2026-05-01 10:00:00"):
            limite.actualizar_limite("diario", nuevo_valor)
            limite.refresh_from_db()

            self.assertEqual(limite.estado_aumento("diario"), "pendiente")
            self.assertEqual(limite.aumento_pendiente_diario, nuevo_valor)
            self.assertEqual(limite.limite_diario, valor_original)

        with freeze_time("2026-05-01 10:05:00"):
            limite.refresh_from_db()
            with self.assertRaises(ValidationError):
                limite.actualizar_limite("diario", Decimal("8888.0000"))

        with freeze_time("2026-05-02 11:00:00"):
            limite.refresh_from_db()
            aplicados = limite.aplicar_aumentos_pendientes()
            limite.refresh_from_db()
            self.assertEqual(aplicados, 1)
            self.assertEqual(limite.limite_diario, nuevo_valor)
            self.assertIsNone(limite.aumento_pendiente_diario)
            self.assertIsNone(limite.estado_aumento("diario"))


class AutoExclusionTest(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="kelly_excl",
            email="kelly_excl@test.com",
            password="pass1234",
            dni=DNI_VALIDO,
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


class RegistroUsuarioSerializerTest(TestCase):
    def test_registro_exige_digito_verificador(self):
        from users.serializers import RegistroUsuarioSerializer

        ser = RegistroUsuarioSerializer(data={
            "username": "nuevo_user",
            "email": "nuevo@test.com",
            "dni": "12345678",
            "fecha_nacimiento": "1995-06-15",
            "password": "Pass1234!",
            "password2": "Pass1234!",
        })
        self.assertFalse(ser.is_valid())
        self.assertIn("digito_verificador", ser.errors)

    def test_registro_valido_con_dni_y_verificador(self):
        from users.serializers import RegistroUsuarioSerializer

        ser = RegistroUsuarioSerializer(data={
            "username": "nuevo_user2",
            "email": "nuevo2@test.com",
            "dni": "12345678",
            "digito_verificador": "1",
            "fecha_nacimiento": "1995-06-15",
            "password": "Pass1234!",
            "password2": "Pass1234!",
        })
        self.assertTrue(ser.is_valid(), ser.errors)
        usuario = ser.save()
        self.assertEqual(usuario.dni, "12345678")
        self.assertEqual(usuario.estado, "pendiente_verificacion")


class LoginKYCWebTest(TestCase):
    def test_registro_no_inicia_sesion_automaticamente(self):
        from django.test import Client

        client = Client()
        resp = client.post("/registro/", {
            "username": "user_kyc_test",
            "email": "kyc@test.com",
            "dni": "12345678",
            "digito_verificador": "1",
            "fecha_nacimiento": "1995-06-15",
            "password": "Pass1234!",
            "password2": "Pass1234!",
        })
        self.assertRedirects(resp, "/login/?registro=ok", fetch_redirect_response=False)
        self.assertFalse("_auth_user_id" in client.session)

    def test_login_rechaza_cuenta_pendiente_verificacion(self):
        from django.test import Client

        Usuario.objects.create_user(
            username="pendiente_login",
            email="pend@test.com",
            password="Pass1234!",
            dni="17801146",
            fecha_nacimiento=date(1995, 6, 15),
            estado="pendiente_verificacion",
        )
        client = Client()
        resp = client.post("/login/", {
            "username": "pendiente_login",
            "password": "Pass1234!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse("_auth_user_id" in client.session)
        self.assertContains(resp, "pendiente de verificación KYC")
