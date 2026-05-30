from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import Usuario, LimiteJuego


@receiver(post_save, sender=Usuario)
def crear_limite_juego(sender, instance, created, **kwargs):
    if created:
        LimiteJuego.objects.get_or_create(usuario=instance)