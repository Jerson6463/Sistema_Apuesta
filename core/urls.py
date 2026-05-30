from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path


# ── Vistas de páginas frontend ────────────────────────────────────────────────
def inicio(request):       return render(request, "inicio.html")
def login_page(request):   return render(request, "login.html")
def registro_page(request):return render(request, "registro.html")
def eventos_page(request): return render(request, "eventos.html")
def wallet_page(request):  return render(request, "wallet.html")
def mis_apuestas_page(request): return render(request, "mis_apuestas.html")

def evento_detalle_page(request, pk):
    return render(request, "eventos.html")   # reutiliza la misma página; JS carga el detalle


urlpatterns = [
    # ── Páginas web (frontend) ────────────────────────────────────────────────
    path("", inicio, name="inicio"),
    path("login/", login_page, name="login"),
    path("registro/", registro_page, name="registro"),
    path("eventos/", eventos_page, name="eventos"),
    path("eventos/<int:pk>/", evento_detalle_page, name="evento_detalle"),
    path("wallet/", wallet_page, name="wallet"),
    path("mis-apuestas/", mis_apuestas_page, name="mis_apuestas"),

    # ── Panel de administración Django ────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── API REST v1 ───────────────────────────────────────────────────────────
    path("api/usuarios/", include("users.urls")),
    path("api/wallet/", include("wallet.urls")),
    path("api/", include("betting.urls")),
    path("api/admin/", include("audit.urls")),
]