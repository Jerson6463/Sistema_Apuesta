import uuid
from decimal import Decimal

from rest_framework import serializers

from betting.models import Apuesta, ApuestaCombinada, Cuota, Evento, Mercado


class CuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cuota
        fields = ("id", "seleccion", "valor", "activa", "actualizado_en")
        read_only_fields = fields


class MercadoSerializer(serializers.ModelSerializer):
    cuotas = CuotaSerializer(many=True, read_only=True)

    class Meta:
        model = Mercado
        fields = (
            "id", "tipo", "estado", "monto_minimo",
            "monto_maximo", "margen_operador", "cuotas",
        )
        read_only_fields = fields


class EventoSerializer(serializers.ModelSerializer):
    mercados = MercadoSerializer(many=True, read_only=True)

    class Meta:
        model = Evento
        fields = (
            "id", "nombre", "deporte", "equipo_local", "equipo_visitante",
            "fecha_inicio", "estado", "mercados",
        )
        read_only_fields = fields


class EventoListSerializer(serializers.ModelSerializer):
    """Versión ligera para listados (sin mercados anidados)."""
    class Meta:
        model = Evento
        fields = ("id", "nombre", "deporte", "equipo_local", "equipo_visitante", "fecha_inicio", "estado")


class CrearApuestaSerializer(serializers.Serializer):
    cuota_id = serializers.IntegerField()
    monto = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    clave_idempotencia = serializers.UUIDField(required=False)

    def validate_cuota_id(self, valor):
        try:
            return Cuota.objects.get(pk=valor, activa=True)
        except Cuota.DoesNotExist:
            raise serializers.ValidationError("Cuota no encontrada o inactiva.")

    def validate(self, data):
        data.setdefault("clave_idempotencia", uuid.uuid4())
        return data


class ApuestaSerializer(serializers.ModelSerializer):
    seleccion = serializers.CharField(source="cuota.seleccion", read_only=True)
    mercado = serializers.CharField(source="cuota.mercado.get_tipo_display", read_only=True)
    evento = serializers.CharField(source="cuota.mercado.evento.nombre", read_only=True)

    class Meta:
        model = Apuesta
        fields = (
            "id", "evento", "mercado", "seleccion",
            "monto_apostado", "cuota_al_apostar", "pago_potencial",
            "estado", "creado_en",
        )
        read_only_fields = fields


class CrearApuestaCombinada(serializers.Serializer):
    cuota_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=2,
        max_length=10,
    )
    monto = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    clave_idempotencia = serializers.UUIDField(required=False)

    def validate_cuota_ids(self, valores):
        cuotas = list(Cuota.objects.filter(pk__in=valores, activa=True))
        if len(cuotas) != len(valores):
            raise serializers.ValidationError("Una o más cuotas no encontradas o inactivas.")
        return cuotas

    def validate(self, data):
        data.setdefault("clave_idempotencia", uuid.uuid4())
        return data


class ApuestaCombinada_Serializer(serializers.ModelSerializer):
    selecciones = CuotaSerializer(many=True, read_only=True)

    class Meta:
        model = ApuestaCombinada
        fields = (
            "id", "selecciones", "monto_apostado",
            "cuota_total", "pago_potencial", "estado", "creado_en",
        )
        read_only_fields = fields


class CashOutSerializer(serializers.Serializer):
    apuesta_id = serializers.UUIDField()
    factor_casa = serializers.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal("0.9000"),
        required=False,
    )
