import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class TipoCuenta(models.TextChoices):
    WALLET_USUARIO = "wallet_usuario", "Wallet del usuario"
    CASA = "casa", "Casa de apuestas"
    APUESTAS_PENDIENTES = "apuestas_pendientes", "Apuestas pendientes"
    BONOS = "bonos", "Bonos promocionales"


class DireccionMovimiento(models.TextChoices):
    DEBITO = "DEBITO", "Débito"
    CREDITO = "CREDITO", "Crédito"


class TipoReferencia(models.TextChoices):
    RECARGA = "recarga", "Recarga de fichas"
    RETIRO = "retiro", "Retiro de fichas"
    APUESTA = "apuesta", "Apuesta"
    PAGO_GANANCIA = "pago_ganancia", "Pago de ganancia"
    PERDIDA = "perdida", "Pérdida a la casa"
    DEVOLUCION = "devolucion", "Devolución por anulación"
    BONO = "bono", "Bono promocional"
    CASH_OUT = "cash_out", "Cash-out anticipado"


class EntradaContable(models.Model):
    """
    Registro de partida doble. Nunca se actualiza ni elimina.
    Toda operación genera al menos dos entradas balanceadas (suma neta = 0).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cuenta = models.CharField(
        max_length=30,
        choices=TipoCuenta.choices,
        verbose_name="Cuenta contable",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entradas_contables",
        verbose_name="Usuario",
    )
    monto = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        verbose_name="Monto",
    )
    direccion = models.CharField(
        max_length=7,
        choices=DireccionMovimiento.choices,
        verbose_name="Dirección",
    )
    id_transaccion = models.UUIDField(
        db_index=True,
        verbose_name="ID de transacción (idempotency key)",
    )
    tipo_referencia = models.CharField(
        max_length=20,
        choices=TipoReferencia.choices,
        verbose_name="Tipo de referencia",
    )
    referencia_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="ID del objeto referenciado",
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado en",
    )

    class Meta:
        verbose_name = "Entrada contable"
        verbose_name_plural = "Entradas contables"
        ordering = ["creado_en"]
        # Garantiza que no existan dos entradas con misma transacción, cuenta y dirección
        # (protección adicional de idempotencia a nivel DB)
        constraints = [
            models.UniqueConstraint(
                fields=["id_transaccion", "cuenta", "direccion"],
                name="unicidad_entrada_transaccion",
            )
        ]

    def __str__(self):
        return (
            f"{self.get_direccion_display()} {self.monto} "
            f"[{self.get_cuenta_display()}] tx={self.id_transaccion}"
        )
