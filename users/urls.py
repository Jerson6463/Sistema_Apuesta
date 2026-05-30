from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.views import (
    AutoExclusionView,
    AutoExclusionesListView,
    LimiteJuegoView,
    PerfilView,
    RegistroView,
    VerificarKYCView,
)

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="api_registro"),
    path("login/", TokenObtainPairView.as_view(), name="api_login"),
    path("login/refresh/", TokenRefreshView.as_view(), name="api_token_refresh"),
    path("perfil/", PerfilView.as_view(), name="api_perfil"),
    path("limites/", LimiteJuegoView.as_view(), name="api_limites"),
    path("autoexclusion/", AutoExclusionView.as_view(), name="api_autoexclusion"),
    path("autoexclusiones/", AutoExclusionesListView.as_view(), name="api_autoexclusiones"),
    path("<int:pk>/verificar-kyc/", VerificarKYCView.as_view(), name="api_verificar_kyc"),
]