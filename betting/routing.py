from django.urls import re_path

from betting.consumers import CuotasEventoConsumer

websocket_urlpatterns = [
    re_path(r"ws/eventos/(?P<evento_id>\d+)/cuotas/$", CuotasEventoConsumer.as_asgi()),
]
