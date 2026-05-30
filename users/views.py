from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
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


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True), name="post")
class RegistroView(generics.CreateAPIView):
    """POST /api/usuarios/registro/ — Registro público. Rate limit: 5/min por IP."""
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


class VerificarKYCView(APIView):
    """
    POST /api/usuarios/<id>/verificar-kyc/
    Solo staff. Aprueba o rechaza la cuenta de un usuario (KYC simulado).
    Body: { "accion": "aprobar" | "rechazar" | "bloquear" }
    """
    permission_classes = [permissions.IsAdminUser]

    TRANSICIONES_VALIDAS = {
        "aprobar": "verificado",
        "rechazar": "pendiente_verificacion",
        "bloquear": "bloqueado",
    }

    def post(self, request, pk):
        try:
            usuario = Usuario.objects.get(pk=pk)
        except Usuario.DoesNotExist:
            return Response({"error": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        accion = request.data.get("accion")
        if accion not in self.TRANSICIONES_VALIDAS:
            return Response(
                {"error": f"Acción inválida. Opciones: {list(self.TRANSICIONES_VALIDAS)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nuevo_estado = self.TRANSICIONES_VALIDAS[accion]
        usuario.estado = nuevo_estado
        usuario.save(update_fields=["estado"])

        return Response({
            "mensaje": f"Usuario {usuario.username} actualizado a '{nuevo_estado}'.",
            "estado_actual": nuevo_estado,
        })
