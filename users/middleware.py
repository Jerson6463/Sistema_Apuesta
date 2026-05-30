"""
Cierra sesiones web de jugadores que aún no completaron KYC o están bloqueados.
"""
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse


class RequiereCuentaVerificadaMiddleware:
    """Redirige al login si un jugador autenticado por sesión no está verificado."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            return self.get_response(request)

        usuario = request.user
        if usuario.is_authenticated and not usuario.is_staff:
            if not usuario.puede_iniciar_sesion():
                logout(request)
                return redirect(f"{reverse('login')}?kyc=pendiente")

        return self.get_response(request)
