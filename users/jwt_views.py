from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class FairBetTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.puede_iniciar_sesion():
            raise serializers.ValidationError(
                {"detail": self.user.mensaje_bloqueo_sesion()}
            )
        return data


class FairBetTokenObtainPairView(TokenObtainPairView):
    serializer_class = FairBetTokenObtainPairSerializer
