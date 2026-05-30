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
    # Registra cuándo se subió cada límite (para aplicar cooldown de 24h)
    fecha_ultimo_aumento_diario = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_aumento_semanal = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_aumento_mensual = models.DateTimeField(null=True, blank=True)

    CAMPO_LIMITE = {
        "diario": ("limite_diario", "fecha_ultimo_aumento_diario"),
        "semanal": ("limite_semanal", "fecha_ultimo_aumento_semanal"),
        "mensual": ("limite_mensual", "fecha_ultimo_aumento_mensual"),
    }

    class Meta:
        verbose_name = "Límite de juego"
        verbose_name_plural = "Límites de juego"

    def actualizar_limite(self, tipo: str, nuevo_valor: Decimal) -> None:
        if tipo not in self.CAMPO_LIMITE:
            raise ValueError(f"Tipo de límite inválido: {tipo}")

        campo_valor, campo_fecha = self.CAMPO_LIMITE[tipo]
        valor_actual = getattr(self, campo_valor)

        if nuevo_valor > valor_actual:
            # Subir el límite requiere cooldown de 24 horas
            fecha_aumento = getattr(self, campo_fecha)
            if fecha_aumento:
                horas_transcurridas = (timezone.now() - fecha_aumento).total_seconds() / 3600
                if horas_transcurridas < self.COOLDOWN_HORAS:
                    horas_restantes = self.COOLDOWN_HORAS - horas_transcurridas
                    raise ValidationError(
                        f"Para aumentar el límite {tipo} debes esperar "
                        f"{horas_restantes:.1f} horas más (cooldown de 24h)."
                    )
            setattr(self, campo_fecha, timezone.now())

        setattr(self, campo_valor, nuevo_valor)
        self.save(update_fields=[campo_valor, campo_fecha])

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