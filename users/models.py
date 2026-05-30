from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.validators import validar_dni_peruano, validar_mayor_de_edad


class EstadoCuenta(models.TextChoices):
    PENDIENTE_VERIFICACION = "pendiente_verificacion", "Pendiente de verificación"
    VERIFICADO = "verificado", "Verificado"
    BLOQUEADO = "bloqueado", "Bloqueado"
    AUTOEXCLUIDO = "autoexcluido", "Autoexcluido"


class Usuario(AbstractUser):
    dni = models.CharField(
        max_length=8,
        unique=True,
        validators=[validar_dni_peruano],
        verbose_name="DNI peruano",
    )
    fecha_nacimiento = models.DateField(verbose_name="Fecha de nacimiento")
    estado = models.CharField(
        max_length=30,
        choices=EstadoCuenta.choices,
        default=EstadoCuenta.PENDIENTE_VERIFICACION,
        verbose_name="Estado de cuenta",
    )

    REQUIRED_FIELDS = AbstractUser.REQUIRED_FIELDS + ["dni", "fecha_nacimiento"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def clean(self):
        super().clean()
        if self.fecha_nacimiento:
            validar_mayor_de_edad(self.fecha_nacimiento)

    def puede_apostar(self) -> bool:
        return self.estado == EstadoCuenta.VERIFICADO

    def puede_iniciar_sesion(self) -> bool:
        """Staff siempre puede entrar; jugadores solo con KYC verificado."""
        if self.is_staff or self.is_superuser:
            return True
        return self.estado == EstadoCuenta.VERIFICADO

    def mensaje_bloqueo_sesion(self) -> str:
        mensajes = {
            EstadoCuenta.PENDIENTE_VERIFICACION: (
                "Tu cuenta está pendiente de verificación KYC. "
                "Un operador debe aprobar tu registro antes de que puedas iniciar sesión."
            ),
            EstadoCuenta.BLOQUEADO: (
                "Tu cuenta está bloqueada. Contacta al soporte de la plataforma."
            ),
            EstadoCuenta.AUTOEXCLUIDO: (
                "Tu cuenta está autoexcluida y no puede acceder en este momento."
            ),
        }
        return mensajes.get(
            self.estado,
            "No puedes iniciar sesión con el estado actual de tu cuenta.",
        )

    def __str__(self):
        return f"{self.username} ({self.get_estado_display()})"


class LimiteJuego(models.Model):
    LIMITE_DIARIO_DEFECTO = Decimal("500.0000")
    LIMITE_SEMANAL_DEFECTO = Decimal("2000.0000")
    LIMITE_MENSUAL_DEFECTO = Decimal("5000.0000")
    COOLDOWN_HORAS = 24

    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name="limite_juego",
    )
    limite_diario = models.DecimalField(
        max_digits=18, decimal_places=4, default=LIMITE_DIARIO_DEFECTO
    )
    limite_semanal = models.DecimalField(
        max_digits=18, decimal_places=4, default=LIMITE_SEMANAL_DEFECTO
    )
    limite_mensual = models.DecimalField(
        max_digits=18, decimal_places=4, default=LIMITE_MENSUAL_DEFECTO
    )
    # Registra cuándo se aplicó cada aumento (tras el cooldown)
    fecha_ultimo_aumento_diario = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_aumento_semanal = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_aumento_mensual = models.DateTimeField(null=True, blank=True)
    # Solicitudes de aumento en período de enfriamiento (estándar industria)
    aumento_pendiente_diario = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    aumento_pendiente_semanal = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    aumento_pendiente_mensual = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    fecha_solicitud_aumento_diario = models.DateTimeField(null=True, blank=True)
    fecha_solicitud_aumento_semanal = models.DateTimeField(null=True, blank=True)
    fecha_solicitud_aumento_mensual = models.DateTimeField(null=True, blank=True)

    CAMPO_LIMITE = {
        "diario": (
            "limite_diario",
            "fecha_ultimo_aumento_diario",
            "aumento_pendiente_diario",
            "fecha_solicitud_aumento_diario",
        ),
        "semanal": (
            "limite_semanal",
            "fecha_ultimo_aumento_semanal",
            "aumento_pendiente_semanal",
            "fecha_solicitud_aumento_semanal",
        ),
        "mensual": (
            "limite_mensual",
            "fecha_ultimo_aumento_mensual",
            "aumento_pendiente_mensual",
            "fecha_solicitud_aumento_mensual",
        ),
    }

    class Meta:
        verbose_name = "Límite de juego"
        verbose_name_plural = "Límites de juego"

    def estado_aumento(self, tipo: str) -> str | None:
        """Retorna 'pendiente' si hay una solicitud de aumento en curso."""
        if tipo not in self.CAMPO_LIMITE:
            raise ValueError(f"Tipo de límite inválido: {tipo}")
        _, _, campo_pendiente, _ = self.CAMPO_LIMITE[tipo]
        if getattr(self, campo_pendiente) is not None:
            return "pendiente"
        return None

    def aplicar_aumentos_pendientes(self) -> int:
        """
        Aplica solicitudes cuyo cooldown de 24h ya venció.
        Retorna la cantidad de límites aplicados.
        """
        ahora = timezone.now()
        campos_actualizar = set()
        aplicados = 0

        for tipo, (
            campo_valor,
            campo_fecha_aplicado,
            campo_pendiente,
            campo_fecha_solicitud,
        ) in self.CAMPO_LIMITE.items():
            valor_pendiente = getattr(self, campo_pendiente)
            fecha_solicitud = getattr(self, campo_fecha_solicitud)
            if valor_pendiente is None or fecha_solicitud is None:
                continue

            horas = (ahora - fecha_solicitud).total_seconds() / 3600
            if horas < self.COOLDOWN_HORAS:
                continue

            setattr(self, campo_valor, valor_pendiente)
            setattr(self, campo_pendiente, None)
            setattr(self, campo_fecha_solicitud, None)
            setattr(self, campo_fecha_aplicado, ahora)
            campos_actualizar.update(
                (campo_valor, campo_pendiente, campo_fecha_solicitud, campo_fecha_aplicado)
            )
            aplicados += 1

        if campos_actualizar:
            self.save(update_fields=sorted(campos_actualizar))
        return aplicados

    def actualizar_limite(self, tipo: str, nuevo_valor: Decimal) -> None:
        if tipo not in self.CAMPO_LIMITE:
            raise ValueError(f"Tipo de límite inválido: {tipo}")

        (
            campo_valor,
            campo_fecha_aplicado,
            campo_pendiente,
            campo_fecha_solicitud,
        ) = self.CAMPO_LIMITE[tipo]
        valor_actual = getattr(self, campo_valor)

        if nuevo_valor <= valor_actual:
            setattr(self, campo_pendiente, None)
            setattr(self, campo_fecha_solicitud, None)
            setattr(self, campo_valor, nuevo_valor)
            self.save(
                update_fields=[campo_valor, campo_pendiente, campo_fecha_solicitud]
            )
            return

        # Subir límite: una solicitud pendiente a la vez (cooldown de la industria)
        if getattr(self, campo_pendiente) is not None:
            raise ValidationError(
                f"Ya existe una solicitud de aumento {tipo} en curso. "
                f"Debes esperar a que se aplique o reducir el límite para cancelarla."
            )

        setattr(self, campo_pendiente, nuevo_valor)
        setattr(self, campo_fecha_solicitud, timezone.now())
        self.save(update_fields=[campo_pendiente, campo_fecha_solicitud])

    def __str__(self):
        return f"Límites de {self.usuario.username}"


class TipoAutoExclusion(models.TextChoices):
    TEMPORAL_7 = "temporal_7", "Temporal 7 días"
    TEMPORAL_30 = "temporal_30", "Temporal 30 días"
    TEMPORAL_90 = "temporal_90", "Temporal 90 días"
    INDEFINIDA = "indefinida", "Indefinida"


DURACION_EXCLUSION_DIAS = {
    TipoAutoExclusion.TEMPORAL_7: 7,
    TipoAutoExclusion.TEMPORAL_30: 30,
    TipoAutoExclusion.TEMPORAL_90: 90,
    TipoAutoExclusion.INDEFINIDA: None,
}


class AutoExclusionManager(models.Manager):
    def crear_exclusion(self, usuario: Usuario, tipo: str) -> "AutoExclusion":
        duracion = DURACION_EXCLUSION_DIAS.get(tipo)
        fecha_fin = (
            timezone.now() + timedelta(days=duracion) if duracion else None
        )
        exclusion = self.create(
            usuario=usuario,
            tipo=tipo,
            fecha_inicio=timezone.now(),
            fecha_fin=fecha_fin,
        )
        usuario.estado = EstadoCuenta.AUTOEXCLUIDO
        usuario.save(update_fields=["estado"])
        return exclusion


class AutoExclusion(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="autoexclusiones",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TipoAutoExclusion.choices,
        verbose_name="Tipo de autoexclusión",
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(
        null=True, blank=True, verbose_name="Fecha de fin (null=indefinida)"
    )

    objects = AutoExclusionManager()

    class Meta:
        verbose_name = "Autoexclusión"
        verbose_name_plural = "Autoexclusiones"
        ordering = ["-fecha_inicio"]

    def esta_activa(self) -> bool:
        if self.fecha_fin is None:
            return True
        return timezone.now() < self.fecha_fin

    def revocar(self) -> None:
        if self.esta_activa():
            raise ValidationError(
                "No puedes revertir la autoexclusión antes de que expire el período."
            )
        self.usuario.estado = EstadoCuenta.VERIFICADO
        self.usuario.save(update_fields=["estado"])

    def __str__(self):
        return f"Autoexclusión {self.tipo} de {self.usuario.username}"
