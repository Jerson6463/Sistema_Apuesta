from datetime import date
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from users.models import AutoExclusion, LimiteJuego, Usuario
from users.validators import validar_dni_peruano, validar_mayor_de_edad


class RegistroUsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label="Confirmar contraseña")

    class Meta:
        model = Usuario
        fields = (
            "username", "email", "first_name", "last_name",
            "dni", "fecha_nacimiento", "password", "password2",
        )

    def validate_dni(self, valor):
        validar_dni_peruano(valor)
        return valor

    def validate_fecha_nacimiento(self, valor):
        validar_mayor_de_edad(valor)
        return valor

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden."})
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
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
    class Meta:
        model = LimiteJuego
        fields = ("limite_diario", "limite_semanal", "limite_mensual")

    def validate(self, data):
        instance = self.instance
        if instance:
            for tipo, campo in [
                ("diario", "limite_diario"),
                ("semanal", "limite_semanal"),
                ("mensual", "limite_mensual"),
            ]:
                if campo in data:
                    nuevo = data[campo]
                    actual = getattr(instance, campo)
                    if nuevo > actual:
                        from django.utils import timezone
                        from django.core.exceptions import ValidationError
                        campo_fecha = f"fecha_ultimo_aumento_{tipo}"
                        fecha = getattr(instance, campo_fecha)
                        if fecha:
                            horas = (timezone.now() - fecha).total_seconds() / 3600
                            if horas < 24:
                                raise serializers.ValidationError(
                                    {campo: f"Cooldown activo. Debes esperar {24-horas:.1f}h más."}
                                )
        return data

    def update(self, instance, validated_data):
        from django.utils import timezone
        for tipo, campo in [
            ("diario", "limite_diario"),
            ("semanal", "limite_semanal"),
            ("mensual", "limite_mensual"),
        ]:
            if campo in validated_data:
                nuevo = validated_data[campo]
                actual = getattr(instance, campo)
                if nuevo > actual:
                    setattr(instance, f"fecha_ultimo_aumento_{tipo}", timezone.now())
                setattr(instance, campo, nuevo)
        instance.save()
        return instance


class AutoExclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoExclusion
        fields = ("tipo", "fecha_inicio", "fecha_fin", "esta_activa")
        read_only_fields = ("fecha_inicio", "fecha_fin", "esta_activa")

    def create(self, validated_data):
        usuario = self.context["request"].user
        return AutoExclusion.objects.crear_exclusion(usuario, validated_data["tipo"])