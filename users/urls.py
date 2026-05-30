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
    path("registro/", RegistroView.as_view(), name="registro"),
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("login/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("perfil/", PerfilView.as_view(), name="perfil"),
    path("limites/", LimiteJuegoView.as_view(), name="limites_juego"),
    path("autoexclusion/", AutoExclusionView.as_view(), name="autoexclusion"),
    path("autoexclusiones/", AutoExclusionesListView.as_view(), name="autoexclusiones_list"),
    path("<int:pk>/verificar-kyc/", VerificarKYCView.as_view(), name="verificar_kyc"),
]