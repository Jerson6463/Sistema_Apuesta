from django.urls import path

from wallet.views import HistorialMovimientosView, RecargaView, RetiroView, SaldoView

urlpatterns = [
    path("saldo/", SaldoView.as_view(), name="wallet_saldo"),
    path("recargar/", RecargaView.as_view(), name="wallet_recargar"),
    path("retirar/", RetiroView.as_view(), name="wallet_retirar"),
    path("historial/", HistorialMovimientosView.as_view(), name="wallet_historial"),
]