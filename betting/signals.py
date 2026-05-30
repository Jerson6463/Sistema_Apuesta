from django.db.models.signals import post_save
from django.dispatch import receiver

from betting.models import Apuesta, HistorialCuota


@receiver(post_save, sender=Apuesta)
def registrar_apuesta_en_auditoria(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from audit.services import registrar_evento
        from audit.models import TipoEventoAuditoria
        registrar_evento(
            tipo=TipoEventoAuditoria.APUESTA,
            payload={
                "apuesta_id": str(instance.id),
                "usuario_id": instance.usuario_id,
                "cuota_id": instance.cuota_id,
                "monto_apostado": str(instance.monto_apostado),
                "cuota_al_apostar": str(instance.cuota_al_apostar),
                "pago_potencial": str(instance.pago_potencial),
                "estado": instance.estado,
            },
            usuario=instance.usuario,
        )
    except Exception:
        pass