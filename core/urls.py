from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path


def inicio(request):
    return render(request, "inicio.html")


urlpatterns = [
    path("", inicio, name="inicio"),
    path("admin/", admin.site.urls),
    # API v1
    path("api/usuarios/", include("users.urls")),
    path("api/wallet/", include("wallet.urls")),
    path("api/", include("betting.urls")),
    path("api/admin/", include("audit.urls")),
]