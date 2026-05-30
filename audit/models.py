import uuid

from django.conf import settings
from django.db import models


class TipoEventoAuditoria(models.TextChoices):
    APUESTA = "apuesta", "Apuesta"
    WALLET = "wallet", "Movimiento de wallet"
    ODDS = "odds", "Cambio de cuota"
    USUARIO = "usuario", "Cambio de usuario/KYC"
    LOGIN = "login", "Autenticación"
    ADMIN = "admin", "Acción de administrador"
    ANTIFRAUDE = "antifraude", "Detección de fraude"


class RegistroAuditoria(models.Model):
    """
    Tabla append-only. Cada registro se encadena con el anterior mediante SHA256.
    hash_actual = SHA256(hash_anterior + JSON(payload))
    NUNCA se actualiza ni elimina un registro.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo_evento = models.CharField(
        max_length=20,
        choices=TipoEventoAuditoria.choices,
        verbose_name="Tipo de evento",
    )
    payload = models.JSONField(verbose_name="Datos del evento")
    hash_anterior = models.CharField(
        max_length=64,
        verbose_name="Hash del registro anterior",
    )
    hash_actual = models.CharField(
        max_length=64,
        verbose_name="Hash de este registro",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_auditoria",
        verbose_name="Usuario",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de auditoría"
        verbose_name_plural = "Registros de auditoría"
        ordering = ["creado_en"]

    def __str__(self):
        return f"[{self.tipo_evento}] {self.hash_actual[:12]}… @ {self.creado_en}"


class ActividadSospechosa(models.Model):
    """Alertas generadas por el motor anti-fraude para revisión manual del admin."""

    TIPO_ALERTA_CHOICES = [
        ("multiples_cuentas_ip", "Múltiples cuentas desde misma IP"),
        ("patron_apuestas_identicas", "Patrón de apuestas idénticas en grupo"),
        ("deposito_cashout_inmediato", "Depósito seguido inmediatamente de cash-out"),
        ("lavado_bonos", "Posible abuso de bonos"),
        ("apuestas_sin_riesgo", "Apuestas sin riesgo (cubriendo todos los resultados)"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alertas_fraude",
        verbose_name="Usuario",
    )
    tipo_alerta = models.CharField(
        max_length=50,
        choices=TIPO_ALERTA_CHOICES,
        verbose_name="Tipo de alerta",
    )
    descripcion = models.TextField(verbose_name="Descripción detallada")
    revisado = models.BooleanField(default=False, verbose_name="Revisado por admin")
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alertas_revisadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    revisado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Actividad sospechosa"
        verbose_name_plural = "Actividades sospechosas"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Alerta '{self.tipo_alerta}' para {self.usuario.username}"
