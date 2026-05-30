from datetime import date
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from users.models import AutoExclusion, LimiteJuego, Usuario
from users.validators import validar_dni_con_verificador, validar_mayor_de_edad


class RegistroUsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label="Confirmar contraseña")
    digito_verificador = serializers.CharField(
        write_only=True,
        max_length=1,
        label="Dígito verificador",
        help_text="Dígito o letra impresa en la esquina del DNI (algoritmo RENIEC).",
    )

    class Meta:
        model = Usuario
        fields = (
            "username", "email", "first_name", "last_name",
            "dni", "digito_verificador", "fecha_nacimiento", "password", "password2",
        )

    def validate_fecha_nacimiento(self, valor):
        validar_mayor_de_edad(valor)
        return valor

    def validate(self, data):
        from django.core.exceptions import ValidationError as DjangoValidationError

        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden."})

        digito = data.pop("digito_verificador", "")
        try:
            validar_dni_con_verificador(data["dni"], digito)
        except DjangoValidationError as exc:
            mensajes = exc.messages if hasattr(exc, "messages") else [str(exc)]
            campo = "digito_verificador" if digito else "dni"
            raise serializers.ValidationError({campo: mensajes})

        return data

    def create(self, validated_data):
        validated_data.pop("password2", None)
        return Usuario.objects.create_user(**validated_data)


class UsuarioPerfilSerializer(serializers.ModelSerializer):
    saldo = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = (
            "id", "username", "email", "first_name", "last_name",
            "dni", "fecha_nacimiento", "estado", "saldo", "date_joined",
            "is_staff", "is_superuser",
        )
        read_only_fields = ("id", "estado", "saldo", "date_joined", "dni", "is_staff", "is_superuser")

    def get_saldo(self, obj):
        from wallet.services import obtener_saldo
        return str(obtener_saldo(obj))


class LimiteJuegoSerializer(serializers.ModelSerializer):
    estado_aumento_diario = serializers.SerializerMethodField()
    estado_aumento_semanal = serializers.SerializerMethodField()
    estado_aumento_mensual = serializers.SerializerMethodField()

    class Meta:
        model = LimiteJuego
        fields = (
            "limite_diario",
            "limite_semanal",
            "limite_mensual",
            "aumento_pendiente_diario",
            "aumento_pendiente_semanal",
            "aumento_pendiente_mensual",
            "estado_aumento_diario",
            "estado_aumento_semanal",
            "estado_aumento_mensual",
        )
        read_only_fields = (
            "aumento_pendiente_diario",
            "aumento_pendiente_semanal",
            "aumento_pendiente_mensual",
            "estado_aumento_diario",
            "estado_aumento_semanal",
            "estado_aumento_mensual",
        )

    def get_estado_aumento_diario(self, obj):
        return obj.estado_aumento("diario")

    def get_estado_aumento_semanal(self, obj):
        return obj.estado_aumento("semanal")

    def get_estado_aumento_mensual(self, obj):
        return obj.estado_aumento("mensual")

    def update(self, instance, validated_data):
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            for tipo, campo in [
                ("diario", "limite_diario"),
                ("semanal", "limite_semanal"),
                ("mensual", "limite_mensual"),
            ]:
                if campo in validated_data:
                    instance.actualizar_limite(tipo, validated_data[campo])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

        instance.refresh_from_db()
        return instance


class AutoExclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoExclusion
        fields = ("tipo", "fecha_inicio", "fecha_fin", "esta_activa")
        read_only_fields = ("fecha_inicio", "fecha_fin", "esta_activa")

    def create(self, validated_data):
        usuario = self.context["request"].user
        return AutoExclusion.objects.crear_exclusion(usuario, validated_data["tipo"])
