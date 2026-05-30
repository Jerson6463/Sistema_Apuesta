from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def inicio(request):
    return JsonResponse({
        "plataforma": "FairBet Lab",
        "descripcion": "Plataforma educativa con moneda virtual. No constituye una casa de apuestas.",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin/",
            "registro": "/api/usuarios/registro/",
            "login": "/api/usuarios/login/",
            "perfil": "/api/usuarios/perfil/",
            "limites": "/api/usuarios/limites/",
            "autoexclusion": "/api/usuarios/autoexclusion/",
            "saldo": "/api/wallet/saldo/",
            "recargar": "/api/wallet/recargar/",
            "retirar": "/api/wallet/retirar/",
            "historial": "/api/wallet/historial/",
            "resumen_mensual": "/api/wallet/resumen/",
            "eventos": "/api/eventos/",
            "apuesta": "/api/apuestas/",
            "apuesta_inplay": "/api/apuestas/in-play/",
            "apuesta_combinada": "/api/apuestas/combinada/",
            "cash_out": "/api/apuestas/cash-out/",
            "mis_apuestas": "/api/apuestas/mis-apuestas/",
            "dashboard_operador": "/api/admin/dashboard/",
            "verificar_integridad": "/api/admin/auditoria/verificar/",
            "reporte_mincetur": "/api/admin/reporte-mincetur/",
            "alertas_fraude": "/api/admin/fraude/alertas/",
        },
        "websocket": "ws://localhost:8000/ws/eventos/<id>/cuotas/",
    })


urlpatterns = [
    path("", inicio, name="inicio"),
    path("admin/", admin.site.urls),
    # API v1
    path("api/usuarios/", include("users.urls")),
    path("api/wallet/", include("wallet.urls")),
    path("api/", include("betting.urls")),
    path("api/admin/", include("audit.urls")),
]