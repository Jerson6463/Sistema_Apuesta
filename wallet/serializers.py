import uuid
from decimal import Decimal

from rest_framework import serializers

from wallet.models import EntradaContable


class EntradaContableSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntradaContable
        fields = (
            "id", "cuenta", "monto", "direccion",
            "tipo_referencia", "referencia_id", "creado_en",
        )
        read_only_fields = fields


class RecargaSerializer(serializers.Serializer):
    monto = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("1.0000"))
    id_transaccion = serializers.UUIDField(required=False)

    def validate_id_transaccion(self, valor):
        return valor or uuid.uuid4()


class RetiroSerializer(serializers.Serializer):
    monto = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("1.0000"))
    id_transaccion = serializers.UUIDField(required=False)

    def validate_id_transaccion(self, valor):
        return valor or uuid.uuid4()


class SaldoSerializer(serializers.Serializer):
    saldo_disponible = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    saldo_bloqueado = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    saldo_total = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
