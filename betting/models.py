import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django_fsm import FSMField, transition


# ── Evento ────────────────────────────────────────────────────────────────────

class EstadoEvento(models.TextChoices):
    PROGRAMADO = "programado", "Programado"
    EN_VIVO = "en_vivo", "En vivo"
    FINALIZADO = "finalizado", "Finalizado"
    SUSPENDIDO = "suspendido", "Suspendido"
    ANULADO = "anulado", "Anulado"


class Evento(models.Model):
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    deporte = models.CharField(max_length=50, verbose_name="Deporte")
    equipo_local = models.CharField(max_length=100, verbose_name="Equipo local")
    equipo_visitante = models.CharField(max_length=100, verbose_name="Equipo visitante")
    fecha_inicio = models.DateTimeField(verbose_name="Fecha de inicio")
    estado = FSMField(
        default=EstadoEvento.PROGRAMADO,
        choices=EstadoEvento.choices,
        protected=True,
        verbose_name="Estado",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"
        ordering = ["fecha_inicio"]

    # ── Transiciones de estado ────────────────────────────────────────────────

    @transition(field=estado, source=EstadoEvento.PROGRAMADO, target=EstadoEvento.EN_VIVO)
    def iniciar(self):
        pass

    @transition(field=estado, source=EstadoEvento.EN_VIVO, target=EstadoEvento.FINALIZADO)
    def finalizar(self):
        pass

    @transition(
        field=estado,
        source=[EstadoEvento.PROGRAMADO, EstadoEvento.EN_VIVO],
        target=EstadoEvento.SUSPENDIDO,
    )
    def suspender(self):
        pass

    @transition(
        field=estado,
        source=[EstadoEvento.SUSPENDIDO, EstadoEvento.EN_VIVO],
        target=EstadoEvento.EN_VIVO,
    )
    def reanudar(self):
        pass

    @transition(
        field=estado,
        source=[EstadoEvento.PROGRAMADO, EstadoEvento.SUSPENDIDO],
        target=EstadoEvento.ANULADO,
    )
    def anular(self):
        pass

    def __str__(self):
        return f"{self.nombre} [{self.get_estado_display()}]"


# ── Mercado ───────────────────────────────────────────────────────────────────

class TipoMercado(models.TextChoices):
    UNO_X_DOS = "1X2", "1X2 (Gana local / Empate / Gana visitante)"
    OVER_UNDER = "over_under", "Over/Under 2.5 goles"
    BTTS = "btts", "Ambos equipos anotan (BTTS)"
    HANDICAP = "handicap", "Hándicap asiático simple"
    GOLEADOR = "goleador", "Goleador exacto"


class EstadoMercado(models.TextChoices):
    ABIERTO = "abierto", "Abierto"
    SUSPENDIDO = "suspendido", "Suspendido"
    CERRADO = "cerrado", "Cerrado"
    LIQUIDADO = "liquidado", "Liquidado"


class Mercado(models.Model):
    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        related_name="mercados",
        verbose_name="Evento",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TipoMercado.choices,
        verbose_name="Tipo de mercado",
    )
    estado = models.CharField(
        max_length=15,
        choices=EstadoMercado.choices,
        default=EstadoMercado.ABIERTO,
        verbose_name="Estado",
    )
    monto_minimo = models.DecimalField(
        max_digits=18, decimal_places=4,
        default=Decimal("1.0000"),
        verbose_name="Monto mínimo",
    )
    monto_maximo = models.DecimalField(
        max_digits=18, decimal_places=4,
        default=Decimal("1000.0000"),
        verbose_name="Monto máximo",
    )
    margen_operador = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal("0.0500"),
        verbose_name="Margen del operador (ej. 0.05 = 5%)",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mercado"
        verbose_name_plural = "Mercados"
        unique_together = [("evento", "tipo")]

    def __str__(self):
        return f"{self.evento} — {self.get_tipo_display()}"


# ── Cuota ─────────────────────────────────────────────────────────────────────

class Cuota(models.Model):
    mercado = models.ForeignKey(
        Mercado,
        on_delete=models.CASCADE,
        related_name="cuotas",
        verbose_name="Mercado",
    )
    seleccion = models.CharField(
        max_length=50,
        verbose_name="Selección",
    )
    valor = models.DecimalField(
        max_digits=18, decimal_places=4,
        verbose_name="Cuota decimal europea",
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cuota"
        verbose_name_plural = "Cuotas"
        unique_together = [("mercado", "seleccion")]

    def __str__(self):
        return f"{self.mercado} | {self.seleccion}: {self.valor}"


# ── Apuesta ───────────────────────────────────────────────────────────────────

class EstadoApuesta(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    ACEPTADA = "aceptada", "Aceptada"
    GANADA = "ganada", "Ganada"
    PERDIDA = "perdida", "Perdida"
    ANULADA = "anulada", "Anulada"
    CASH_OUT = "cash_out", "Cash-out"


class Apuesta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="apuestas",
        verbose_name="Usuario",
    )
    cuota = models.ForeignKey(
        Cuota,
        on_delete=models.PROTECT,
        related_name="apuestas",
        verbose_name="Cuota seleccionada",
    )
    monto_apostado = models.DecimalField(
        max_digits=18, decimal_places=4,
        verbose_name="Monto apostado",
    )
    # Snapshot de la cuota al momento de apostar (inmutable)
    cuota_al_apostar = models.DecimalField(
        max_digits=18, decimal_places=4,
        verbose_name="Cuota al momento de apostar",
    )
    pago_potencial = models.DecimalField(
        max_digits=18, decimal_places=4,
        verbose_name="Pago potencial (stake × odds)",
    )
    clave_idempotencia = models.UUIDField(
        unique=True,
        verbose_name="Clave de idempotencia",
    )
    estado = FSMField(
        default=EstadoApuesta.ACEPTADA,
        choices=EstadoApuesta.choices,
        protected=True,
        verbose_name="Estado",
    )
    ip_origen = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name="IP de origen",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Apuesta"
        verbose_name_plural = "Apuestas"
        ordering = ["-creado_en"]

    # ── Transiciones de estado ────────────────────────────────────────────────

    @transition(field=estado, source=EstadoApuesta.ACEPTADA, target=EstadoApuesta.GANADA)
    def marcar_ganada(self):
        pass

    @transition(field=estado, source=EstadoApuesta.ACEPTADA, target=EstadoApuesta.PERDIDA)
    def marcar_perdida(self):
        pass

    @transition(field=estado, source=EstadoApuesta.ACEPTADA, target=EstadoApuesta.ANULADA)
    def marcar_anulada(self):
        pass

    @transition(field=estado, source=EstadoApuesta.ACEPTADA, target=EstadoApuesta.CASH_OUT)
    def marcar_cash_out(self):
        pass

    def __str__(self):
        return (
            f"Apuesta {self.id} | {self.usuario.username} "
            f"| {self.monto_apostado}×{self.cuota_al_apostar} "
            f"[{self.get_estado_display()}]"
        )


# ── Apuesta Combinada ─────────────────────────────────────────────────────────

class ApuestaCombinada(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="apuestas_combinadas",
        verbose_name="Usuario",
    )
    selecciones = models.ManyToManyField(
        Cuota,
        related_name="combinadas",
        verbose_name="Selecciones",
    )
    monto_apostado = models.DecimalField(
        max_digits=18, decimal_places=4,
        verbose_name="Monto apostado",
    )
    cuota_total = models.DecimalField(
        max_digits=18, decimal_places=4,
        verbose_name="Cuota total (producto)",
    )
    pago_potencial = models.DecimalField(
        max_digits=18, decimal_places=4,
        verbose_name="Pago potencial",
    )
    clave_idempotencia = models.UUIDField(unique=True)
    estado = FSMField(
        default=EstadoApuesta.ACEPTADA,
        choices=EstadoApuesta.choices,
        protected=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Apuesta combinada"
        verbose_name_plural = "Apuestas combinadas"

    @transition(field=estado, source=EstadoApuesta.ACEPTADA, target=EstadoApuesta.GANADA)
    def marcar_ganada(self):
        pass

    @transition(field=estado, source=EstadoApuesta.ACEPTADA, target=EstadoApuesta.PERDIDA)
    def marcar_perdida(self):
        pass

    @transition(field=estado, source=EstadoApuesta.ACEPTADA, target=EstadoApuesta.ANULADA)
    def marcar_anulada(self):
        pass

    def __str__(self):
        return f"Combinada {self.id} | {self.usuario.username} [{self.get_estado_display()}]"


# ── Historial de cuotas ───────────────────────────────────────────────────────

class HistorialCuota(models.Model):
    """Registro inmutable de cada cambio de cuota (para auditoría)."""
    cuota = models.ForeignKey(
        Cuota,
        on_delete=models.CASCADE,
        related_name="historial",
    )
    valor_anterior = models.DecimalField(max_digits=18, decimal_places=4)
    valor_nuevo = models.DecimalField(max_digits=18, decimal_places=4)
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de cuota"
        verbose_name_plural = "Historial de cuotas"
        ordering = ["-registrado_en"]