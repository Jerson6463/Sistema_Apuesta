from django.urls import path

from betting.views import (
    ActualizarCuotaView,
    AgregarMercadoView,
    ApuestaInPlayView,
    CashOutView,
    CrearApuestaCombinada_View,
    CrearApuestaView,
    CrearEventoView,
    EditarUsuarioAdminView,
    EventoDetalleView,
    EventoListView,
    ListarUsuariosView,
    MisApuestasView,
)

urlpatterns = [
    path("eventos/", EventoListView.as_view(), name="eventos_list"),
    path("eventos/crear/", CrearEventoView.as_view(), name="crear_evento"),
    path("eventos/<int:pk>/", EventoDetalleView.as_view(), name="api_evento_detalle"),
    path("eventos/<int:pk>/mercados/", AgregarMercadoView.as_view(), name="agregar_mercado"),
    path("apuestas/", CrearApuestaView.as_view(), name="crear_apuesta"),
    path("apuestas/in-play/", ApuestaInPlayView.as_view(), name="apuesta_in_play"),
    path("apuestas/mis-apuestas/", MisApuestasView.as_view(), name="api_mis_apuestas"),
    path("apuestas/cash-out/", CashOutView.as_view(), name="cash_out"),
    path("apuestas/combinada/", CrearApuestaCombinada_View.as_view(), name="apuesta_combinada"),
    path("eventos/<int:evento_id>/cuotas/<int:cuota_id>/", ActualizarCuotaView.as_view(), name="actualizar_cuota"),
    path("admin/usuarios/", ListarUsuariosView.as_view(), name="listar_usuarios"),
    path("admin/usuarios/<int:pk>/", EditarUsuarioAdminView.as_view(), name="editar_usuario_admin"),
]