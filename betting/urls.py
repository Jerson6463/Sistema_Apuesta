from django.urls import path

from betting.views import (
    ApuestaInPlayView,
    CashOutView,
    CrearApuestaCombinada_View,
    CrearApuestaView,
    EventoDetalleView,
    EventoListView,
    MisApuestasView,
)

urlpatterns = [
    path("eventos/", EventoListView.as_view(), name="eventos_list"),
    path("eventos/<int:pk>/", EventoDetalleView.as_view(), name="evento_detalle"),
    path("apuestas/", CrearApuestaView.as_view(), name="crear_apuesta"),
    path("apuestas/in-play/", ApuestaInPlayView.as_view(), name="apuesta_in_play"),
    path("apuestas/mis-apuestas/", MisApuestasView.as_view(), name="mis_apuestas"),
    path("apuestas/cash-out/", CashOutView.as_view(), name="cash_out"),
    path("apuestas/combinada/", CrearApuestaCombinada_View.as_view(), name="apuesta_combinada"),
]