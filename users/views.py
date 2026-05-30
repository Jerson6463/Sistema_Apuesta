from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import AutoExclusion, LimiteJuego, Usuario
from users.serializers import (
    AutoExclusionSerializer,
    LimiteJuegoSerializer,
    RegistroUsuarioSerializer,
    UsuarioPerfilSerializer,
)


class RegistroView(generics.CreateAPIView):
    """POST /api/usuarios/registro/ — Registro público."""
    queryset = Usuario.objects.all()
    serializer_class = RegistroUsuarioSerializer
    permission_classes = [permissions.AllowAny]


class PerfilView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/usuarios/perfil/ — Perfil del usuario autenticado."""
    serializer_class = UsuarioPerfilSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LimiteJuegoView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/usuarios/limites/ — Límites de juego."""
    serializer_class = LimiteJuegoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        limite, _ = LimiteJuego.objects.get_or_create(usuario=self.request.user)
        return limite


class AutoExclusionView(generics.CreateAPIView):
    """POST /api/usuarios/autoexclusion/ — Solicitar autoexclusión."""
    serializer_class = AutoExclusionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


class AutoExclusionesListView(generics.ListAPIView):
    """GET /api/usuarios/autoexclusiones/ — Historial de autoexclusiones."""
    serializer_class = AutoExclusionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AutoExclusion.objects.filter(usuario=self.request.user)