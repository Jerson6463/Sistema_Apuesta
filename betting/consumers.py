"""
WebSocket consumer para cuotas en tiempo real por evento.

Protocolo:
  - Cliente se conecta a ws://host/ws/eventos/<evento_id>/cuotas/
  - Al conectar recibe el estado actual de todas las cuotas del evento.
  - Cuando un admin actualiza una cuota (vía registrar_cambio_cuota),
    Celery publica en el canal del grupo y todos los suscriptores reciben la actualización.
  - Si la cuota cambió mientras el usuario tenía el ticket abierto,
    el frontend debe pedir reconfirmación antes de aceptar la apuesta.
"""
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from betting.models import Cuota, Evento


class CuotasEventoConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.evento_id = self.scope["url_route"]["kwargs"]["evento_id"]
        self.grupo = f"evento_{self.evento_id}_cuotas"

        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

        # Enviar estado actual de todas las cuotas al conectar
        cuotas = await self._obtener_cuotas()
        await self.send(text_data=json.dumps({"tipo": "estado_inicial", "cuotas": cuotas}))

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # El cliente no envía mensajes en este canal (solo escucha)
        pass

    async def cuota_actualizada(self, event):
        """Recibe el mensaje del grupo cuando una cuota cambia."""
        await self.send(text_data=json.dumps({
            "tipo": "cuota_actualizada",
            "cuota_id": event["cuota_id"],
            "seleccion": event["seleccion"],
            "valor_anterior": event["valor_anterior"],
            "valor_nuevo": event["valor_nuevo"],
            "aviso": "La cuota cambió. Confirme la nueva cuota para continuar.",
        }))

    @database_sync_to_async
    def _obtener_cuotas(self):
        cuotas = Cuota.objects.filter(
            mercado__evento_id=self.evento_id, activa=True
        ).select_related("mercado")
        return [
            {
                "cuota_id": c.id,
                "mercado": c.mercado.get_tipo_display(),
                "seleccion": c.seleccion,
                "valor": str(c.valor),
            }
            for c in cuotas
        ]
