"""
Tests de la auditoría inmutable con encadenamiento por hash SHA256.
"""
import hashlib
import json

from django.test import TestCase

from audit.models import RegistroAuditoria, TipoEventoAuditoria
from audit.services import registrar_evento, verificar_integridad_cadena


class CadenaHashTest(TestCase):
    def test_primer_registro_tiene_hash_genesis(self):
        reg = registrar_evento(
            tipo=TipoEventoAuditoria.APUESTA,
            payload={"accion": "creacion", "monto": "100.0000"},
        )
        self.assertIsNotNone(reg.hash_actual)
        self.assertEqual(len(reg.hash_actual), 64)  # SHA256 = 64 hex chars

    def test_encadenamiento_hash_es_correcto(self):
        reg1 = registrar_evento(
            tipo=TipoEventoAuditoria.WALLET,
            payload={"accion": "recarga", "monto": "500.0000"},
        )
        reg2 = registrar_evento(
            tipo=TipoEventoAuditoria.APUESTA,
            payload={"accion": "creacion", "monto": "50.0000"},
        )
        # hash_reg2 = SHA256(hash_reg1 + payload_reg2)
        datos = reg1.hash_actual + json.dumps(reg2.payload, sort_keys=True)
        hash_esperado = hashlib.sha256(datos.encode()).hexdigest()
        self.assertEqual(reg2.hash_actual, hash_esperado)

    def test_cadena_integra_pasa_verificacion(self):
        for i in range(5):
            registrar_evento(
                tipo=TipoEventoAuditoria.ODDS,
                payload={"cuota_id": i, "valor": "2.5000"},
            )
        es_valida, _ = verificar_integridad_cadena()
        self.assertTrue(es_valida)

    def test_cadena_manipulada_falla_verificacion(self):
        reg = registrar_evento(
            tipo=TipoEventoAuditoria.APUESTA,
            payload={"accion": "creacion"},
        )
        registrar_evento(
            tipo=TipoEventoAuditoria.WALLET,
            payload={"accion": "retiro"},
        )
        # Manipulación directa (bypass del ORM para simular fraude)
        RegistroAuditoria.objects.filter(pk=reg.pk).update(
            payload={"accion": "MANIPULADO"}
        )
        es_valida, errores = verificar_integridad_cadena()
        self.assertFalse(es_valida)
        self.assertGreater(len(errores), 0)

    def test_registro_es_append_only(self):
        """El admin no debe poder editar ni eliminar entradas de auditoría."""
        from audit.admin import RegistroAuditoriaAdmin
        from django.contrib.admin.sites import AdminSite
        admin_instance = RegistroAuditoriaAdmin(RegistroAuditoria, AdminSite())
        self.assertFalse(admin_instance.has_change_permission(None))
        self.assertFalse(admin_instance.has_delete_permission(None))
        self.assertFalse(admin_instance.has_add_permission(None))


class ActividadSospechosaTest(TestCase):
    def test_se_puede_crear_alerta(self):
        from audit.models import ActividadSospechosa
        from datetime import date
        from users.models import Usuario

        usuario = Usuario.objects.create_user(
            username="kelly_fraud",
            email="fraud@test.com",
            password="pass1234",
            dni="12345678",
            fecha_nacimiento=date(1995, 1, 1),
        )
        alerta = ActividadSospechosa.objects.create(
            usuario=usuario,
            tipo_alerta="multiples_cuentas_ip",
            descripcion="Misma IP con 3 cuentas distintas en 1 hora.",
        )
        self.assertFalse(alerta.revisado)
        self.assertEqual(alerta.tipo_alerta, "multiples_cuentas_ip")