"""
Vistas del dashboard del operador y auditoría.
Solo accesibles para is_staff=True.
"""
import csv
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import ActividadSospechosa, RegistroAuditoria
from audit.services import verificar_integridad_cadena


class EsOperador(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class DashboardOperadorView(APIView):
    """
    GET /api/admin/dashboard/
    Métricas en vivo: GGR, exposure por evento, volumen, usuarios activos.
    """
    permission_classes = [EsOperador]

    def get(self, request):
        from django.db.models import Sum, Count
        from betting.models import Apuesta, EstadoApuesta
        from wallet.models import EntradaContable, TipoReferencia, DireccionMovimiento

        total_stakes = (
            EntradaContable.objects.filter(
                tipo_referencia=TipoReferencia.APUESTA,
                direccion=DireccionMovimiento.DEBITO,
            ).aggregate(total=Sum("monto"))["total"] or Decimal("0")
        )
        total_payouts = (
            EntradaContable.objects.filter(
                tipo_referencia=TipoReferencia.PAGO_GANANCIA,
                direccion=DireccionMovimiento.CREDITO,
            ).aggregate(total=Sum("monto"))["total"] or Decimal("0")
        )
        ggr = total_stakes - total_payouts

        hace_24h = timezone.now() - timezone.timedelta(hours=24)
        usuarios_activos = (
            Apuesta.objects.filter(creado_en__gte=hace_24h)
            .values("usuario").distinct().count()
        )
        volumen = Apuesta.objects.filter(
            estado__in=[
                EstadoApuesta.ACEPTADA, EstadoApuesta.GANADA,
                EstadoApuesta.PERDIDA, EstadoApuesta.CASH_OUT,
            ]
        ).count()
        alertas_pendientes = ActividadSospechosa.objects.filter(revisado=False).count()
        exposure = self._calcular_exposure()

        return Response({
            "ggr": str(ggr),
            "total_stakes": str(total_stakes),
            "total_payouts": str(total_payouts),
            "usuarios_activos_24h": usuarios_activos,
            "volumen_apuestas": volumen,
            "alertas_fraude_pendientes": alertas_pendientes,
            "exposure_por_evento": exposure,
        })

    def _calcular_exposure(self):
        from betting.models import Apuesta, EstadoApuesta
        from django.db.models import Sum

        resultado = {}
        apuestas = (
            Apuesta.objects.filter(estado=EstadoApuesta.ACEPTADA)
            .values("cuota__mercado__evento__nombre", "cuota__seleccion")
            .annotate(exposure=Sum("pago_potencial"))
        )
        for row in apuestas:
            evento = row["cuota__mercado__evento__nombre"]
            seleccion = row["cuota__seleccion"]
            if evento not in resultado:
                resultado[evento] = {}
            resultado[evento][seleccion] = str(row["exposure"])
        return resultado


class ReporteMINCETURView(APIView):
    """
    GET /api/admin/reporte-mincetur/?mes=5&anio=2026
    CSV mensual estilo MINCETUR (DS 005-2023-MINCETUR).
    """
    permission_classes = [EsOperador]

    def get(self, request):
        mes = int(request.query_params.get("mes", timezone.now().month))
        anio = int(request.query_params.get("anio", timezone.now().year))

        from betting.models import Apuesta
        apuestas = Apuesta.objects.filter(
            creado_en__month=mes, creado_en__year=anio
        ).select_related("usuario", "cuota__mercado__evento")

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="reporte_mincetur_{anio}_{mes:02d}.csv"'
        )
        response.write("﻿")  # BOM UTF-8 para Excel

        writer = csv.writer(response)
        writer.writerow([
            "ID_APUESTA", "FECHA", "USUARIO_DNI", "EVENTO",
            "MERCADO", "SELECCION", "MONTO_APOSTADO",
            "CUOTA", "PAGO_POTENCIAL", "ESTADO",
        ])
        for apuesta in apuestas:
            writer.writerow([
                str(apuesta.id),
                apuesta.creado_en.strftime("%Y-%m-%d %H:%M:%S"),
                apuesta.usuario.dni,
                apuesta.cuota.mercado.evento.nombre,
                apuesta.cuota.mercado.get_tipo_display(),
                apuesta.cuota.seleccion,
                str(apuesta.monto_apostado),
                str(apuesta.cuota_al_apostar),
                str(apuesta.pago_potencial),
                apuesta.estado,
            ])
        return response


class VerificarIntegridadView(APIView):
    """GET /api/admin/auditoria/verificar/ — Verifica cadena SHA256."""
    permission_classes = [EsOperador]

    def get(self, request):
        es_valida, errores = verificar_integridad_cadena()
        total = RegistroAuditoria.objects.count()
        return Response(
            {"integra": es_valida, "total_registros": total, "errores": errores},
            status=status.HTTP_200_OK if es_valida else status.HTTP_409_CONFLICT,
        )


class AlertasFraudeView(APIView):
    """GET /api/admin/fraude/alertas/ — Alertas anti-fraude pendientes."""
    permission_classes = [EsOperador]

    def get(self, request):
        solo_pendientes = request.query_params.get("pendientes", "true") == "true"
        qs = ActividadSospechosa.objects.select_related("usuario")
        if solo_pendientes:
            qs = qs.filter(revisado=False)
        data = [
            {
                "id": a.id,
                "usuario": a.usuario.username,
                "tipo_alerta": a.tipo_alerta,
                "descripcion": a.descripcion,
                "revisado": a.revisado,
                "creado_en": a.creado_en.isoformat(),
            }
            for a in qs[:100]
        ]
        return Response(data)