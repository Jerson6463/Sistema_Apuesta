from decimal import Decimal

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from betting.exceptions import (
    ApuestaYaLiquidadaError,
    CashOutNoDisponibleError,
    EventoNoDisponibleError,
    MercadoCerradoError,
    MontoFueraDeRangoError,
    SeleccionMutuamenteExcluyenteError,
    UsuarioNoHabilitadoError,
)
from betting.models import Apuesta, ApuestaCombinada, Evento, EstadoEvento
from betting.serializers import (
    ApuestaCombinada_Serializer,
    ApuestaSerializer,
    CashOutSerializer,
    CrearApuestaCombinada,
    CrearApuestaSerializer,
    EventoListSerializer,
    EventoSerializer,
)
from betting.services import (
    crear_apuesta,
    crear_apuesta_combinada,
    hacer_cash_out,
)
from wallet.exceptions import SaldoInsuficienteError


class EventoListView(generics.ListAPIView):
    """GET /api/eventos/ — Lista eventos disponibles para apostar."""
    serializer_class = EventoListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Evento.objects.all()
        estado = self.request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        return qs.order_by("fecha_inicio")


class EventoDetalleView(generics.RetrieveAPIView):
    """GET /api/eventos/<id>/ — Detalle del evento con mercados y cuotas."""
    serializer_class = EventoSerializer
    queryset = Evento.objects.prefetch_related("mercados__cuotas")
    permission_classes = [permissions.IsAuthenticated]


class CrearApuestaView(APIView):
    """
    POST /api/apuestas/ — Crea una apuesta simple.
    Requiere: cuota_id, monto, (opcional) clave_idempotencia.
    Mensaje de consumo responsable siempre presente en la respuesta.
    """
    permission_classes = [permissions.IsAuthenticated]

    MENSAJE_RESPONSABLE = (
        "Apuesta con responsabilidad. Fija un límite antes de jugar. "
        "Plataforma educativa con moneda virtual. No constituye una casa de apuestas."
    )

    def post(self, request):
        serializer = CrearApuestaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        ip = request.META.get("REMOTE_ADDR")
        try:
            apuesta = crear_apuesta(
                usuario=request.user,
                cuota=datos["cuota_id"],
                monto=datos["monto"],
                clave_idempotencia=datos["clave_idempotencia"],
                ip_origen=ip,
            )
        except UsuarioNoHabilitadoError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except (EventoNoDisponibleError, MercadoCerradoError, MontoFueraDeRangoError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except SaldoInsuficienteError as e:
            return Response({"error": str(e)}, status=status.HTTP_402_PAYMENT_REQUIRED)

        return Response({
            "apuesta": ApuestaSerializer(apuesta).data,
            "aviso_responsable": self.MENSAJE_RESPONSABLE,
        }, status=status.HTTP_201_CREATED)


class MisApuestasView(generics.ListAPIView):
    """GET /api/apuestas/mis-apuestas/ — Apuestas del usuario autenticado."""
    serializer_class = ApuestaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Apuesta.objects.filter(usuario=self.request.user).select_related(
            "cuota__mercado__evento"
        )


class CashOutView(APIView):
    """POST /api/apuestas/cash-out/ — Cierra anticipadamente una apuesta."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CashOutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        try:
            apuesta = Apuesta.objects.get(
                id=datos["apuesta_id"], usuario=request.user
            )
        except Apuesta.DoesNotExist:
            return Response({"error": "Apuesta no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        factor = datos.get("factor_casa", Decimal("0.9000"))
        try:
            monto_cashout = hacer_cash_out(apuesta, factor_casa=factor)
        except CashOutNoDisponibleError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "mensaje": "Cash-out realizado con éxito.",
            "monto_recibido": str(monto_cashout),
        })


class CrearApuestaCombinada_View(APIView):
    """
    POST /api/apuestas/combinada/ — Crea una apuesta acumuladora.
    Valida que no haya selecciones del mismo mercado.
    """
    permission_classes = [permissions.IsAuthenticated]

    MENSAJE_RESPONSABLE = (
        "Apuesta con responsabilidad. Las combinadas multiplican el riesgo. "
        "Plataforma educativa con moneda virtual. No constituye una casa de apuestas."
    )

    def post(self, request):
        serializer = CrearApuestaCombinada(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        try:
            combinada = crear_apuesta_combinada(
                usuario=request.user,
                cuotas=datos["cuota_ids"],
                monto=datos["monto"],
                clave_idempotencia=datos["clave_idempotencia"],
                ip_origen=request.META.get("REMOTE_ADDR"),
            )
        except UsuarioNoHabilitadoError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except SeleccionMutuamenteExcluyenteError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except SaldoInsuficienteError as e:
            return Response({"error": str(e)}, status=status.HTTP_402_PAYMENT_REQUIRED)

        return Response({
            "combinada": ApuestaCombinada_Serializer(combinada).data,
            "aviso_responsable": self.MENSAJE_RESPONSABLE,
        }, status=status.HTTP_201_CREATED)