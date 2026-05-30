import uuid
from decimal import Decimal

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from wallet.exceptions import LimiteSuperadoError, SaldoInsuficienteError
from wallet.models import EntradaContable
from wallet.serializers import (
    EntradaContableSerializer,
    RecargaSerializer,
    RetiroSerializer,
    SaldoSerializer,
)
from wallet.services import (
    obtener_saldo,
    obtener_saldo_bloqueado,
    recargar_fichas,
    retirar_fichas,
)


class SaldoView(APIView):
    """GET /api/wallet/saldo/ — Consulta de saldo disponible y bloqueado."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        usuario = request.user
        disponible = obtener_saldo(usuario)
        bloqueado = obtener_saldo_bloqueado(usuario)
        return Response({
            "saldo_disponible": str(disponible),
            "saldo_bloqueado": str(bloqueado),
            "saldo_total": str(disponible + bloqueado),
        })


class RecargaView(APIView):
    """POST /api/wallet/recargar/ — Simula una recarga de fichas virtuales."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RecargaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        id_tx = datos.get("id_transaccion") or uuid.uuid4()
        try:
            recargar_fichas(request.user, datos["monto"], id_transaccion=id_tx)
        except LimiteSuperadoError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "mensaje": "Recarga exitosa.",
            "id_transaccion": str(id_tx),
            "saldo_disponible": str(obtener_saldo(request.user)),
        }, status=status.HTTP_201_CREATED)


class RetiroView(APIView):
    """POST /api/wallet/retirar/ — Simula un retiro de fichas virtuales."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RetiroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        id_tx = datos.get("id_transaccion") or uuid.uuid4()
        try:
            retirar_fichas(request.user, datos["monto"], id_transaccion=id_tx)
        except SaldoInsuficienteError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "mensaje": "Retiro exitoso.",
            "id_transaccion": str(id_tx),
            "saldo_disponible": str(obtener_saldo(request.user)),
        }, status=status.HTTP_201_CREATED)


class HistorialMovimientosView(APIView):
    """GET /api/wallet/historial/ — Movimientos del wallet del usuario."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        entradas = EntradaContable.objects.filter(
            usuario=request.user,
            cuenta="wallet_usuario",
        ).order_by("-creado_en")[:50]
        serializer = EntradaContableSerializer(entradas, many=True)
        return Response(serializer.data)