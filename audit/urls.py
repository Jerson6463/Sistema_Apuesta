from django.urls import path

from audit.views import (
    AlertasFraudeView,
    DashboardOperadorView,
    ReporteMINCETURView,
    VerificarIntegridadView,
)

urlpatterns = [
    path("dashboard/", DashboardOperadorView.as_view(), name="dashboard_operador"),
    path("reporte-mincetur/", ReporteMINCETURView.as_view(), name="reporte_mincetur"),
    path("auditoria/verificar/", VerificarIntegridadView.as_view(), name="verificar_integridad"),
    path("fraude/alertas/", AlertasFraudeView.as_view(), name="alertas_fraude"),
]
