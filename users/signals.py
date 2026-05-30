from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import Usuario, LimiteJuego


@receiver(post_save, sender=Usuario)
def crear_limite_juego(sender, instance, created, **kwargs):
    if created:
        LimiteJuego.objects.get_or_create(usuario=instance)


@receiver(post_save, sender=Usuario)
def registrar_cambio_estado_auditoria(sender, instance, created, **kwargs):
    if created:
        return
    try:
        from audit.services import registrar_evento
        from audit.models import TipoEventoAuditoria
        registrar_evento(
            tipo=TipoEventoAuditoria.USUARIO,
            payload={
                "accion": "cambio_estado",
                "usuario_id": instance.id,
                "username": instance.username,
                "nuevo_estado": instance.estado,
            },
            usuario=instance,
        )
    except Exception:
        pass
