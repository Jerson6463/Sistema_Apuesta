from decimal import Decimal

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
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


@method_decorator(ratelimit(key="user", rate="10/m", method="POST", block=True), name="post")
class CrearApuestaView(APIView):
    """
    POST /api/apuestas/ — Crea una apuesta simple.
    Rate limit: 10 apuestas/min por usuario (control de juego responsable).
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


class ActualizarCuotaView(APIView):
    """
    PATCH /api/eventos/<evento_id>/cuotas/<cuota_id>/
    Solo staff. Actualiza el valor de una cuota y notifica a todos los
    clientes WebSocket suscritos al canal del evento.
    """
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, evento_id, cuota_id):
        from betting.models import Cuota
        from betting.services import registrar_cambio_cuota
        from decimal import Decimal as Dec

        try:
            cuota = Cuota.objects.select_related("mercado__evento").get(
                pk=cuota_id, mercado__evento_id=evento_id
            )
        except Cuota.DoesNotExist:
            return Response({"error": "Cuota no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        nuevo_valor = request.data.get("valor")
        if not nuevo_valor:
            return Response({"error": "El campo 'valor' es requerido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            nuevo_valor_decimal = Dec(str(nuevo_valor))
        except Exception:
            return Response({"error": "Valor de cuota inválido."}, status=status.HTTP_400_BAD_REQUEST)

        if nuevo_valor_decimal <= Dec("1.0000"):
            return Response({"error": "La cuota debe ser mayor a 1.00."}, status=status.HTTP_400_BAD_REQUEST)

        valor_anterior = cuota.valor
        registrar_cambio_cuota(cuota, nuevo_valor_decimal)

        return Response({
            "mensaje": "Cuota actualizada. Los clientes WebSocket han sido notificados.",
            "cuota_id": cuota_id,
            "valor_anterior": str(valor_anterior),
            "valor_nuevo": str(nuevo_valor_decimal),
        })


class ApuestaInPlayView(APIView):
    """
    POST /api/apuestas/in-play/
    Apuesta mientras el evento está EN_VIVO con cuotas dinámicas.
    El mercado debe estar ABIERTO (no suspendido por evento crítico).
    Incluye mensaje de consumo responsable obligatorio.
    """
    permission_classes = [permissions.IsAuthenticated]

    MENSAJE_RESPONSABLE = (
        "Apuesta en vivo con responsabilidad. Las cuotas cambian constantemente. "
        "Plataforma educativa con moneda virtual. No constituye una casa de apuestas."
    )

    def post(self, request):
        from betting.models import Cuota, EstadoEvento, EstadoMercado
        from betting.exceptions import EventoNoDisponibleError, MercadoCerradoError
        import uuid as uuid_mod

        cuota_id = request.data.get("cuota_id")
        monto = request.data.get("monto")
        clave = request.data.get("clave_idempotencia", str(uuid_mod.uuid4()))

        if not cuota_id or not monto:
            return Response({"error": "cuota_id y monto son requeridos."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cuota = Cuota.objects.select_related("mercado__evento").get(pk=cuota_id, activa=True)
        except Cuota.DoesNotExist:
            return Response({"error": "Cuota no encontrada o inactiva."}, status=status.HTTP_404_NOT_FOUND)

        evento = cuota.mercado.evento
        if evento.estado != EstadoEvento.EN_VIVO:
            return Response(
                {"error": "Este endpoint solo acepta apuestas en eventos EN VIVO."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cuota.mercado.estado != EstadoMercado.ABIERTO:
            return Response(
                {"error": "Mercado suspendido temporalmente por evento crítico. Intente en unos segundos."},
                status=status.HTTP_423_LOCKED,
            )

        from decimal import Decimal as Dec
        from betting.services import crear_apuesta
        from betting.exceptions import UsuarioNoHabilitadoError, MontoFueraDeRangoError
        from wallet.exceptions import SaldoInsuficienteError

        try:
            apuesta = crear_apuesta(
                usuario=request.user,
                cuota=cuota,
                monto=Dec(str(monto)),
                clave_idempotencia=uuid_mod.UUID(str(clave)),
                ip_origen=request.META.get("REMOTE_ADDR"),
            )
        except UsuarioNoHabilitadoError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except (MontoFueraDeRangoError, MercadoCerradoError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except SaldoInsuficienteError as e:
            return Response({"error": str(e)}, status=status.HTTP_402_PAYMENT_REQUIRED)

        return Response({
            "apuesta": ApuestaSerializer(apuesta).data,
            "aviso_responsable": self.MENSAJE_RESPONSABLE,
        }, status=status.HTTP_201_CREATED)


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