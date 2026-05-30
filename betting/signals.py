from django.db.models.signals import post_save
from django.dispatch import receiver

from betting.models import Apuesta, HistorialCuota


@receiver(post_save, sender=HistorialCuota)
def registrar_cambio_cuota_en_auditoria(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from audit.services import registrar_evento
        from audit.models import TipoEventoAuditoria
        registrar_evento(
            tipo=TipoEventoAuditoria.ODDS,
            payload={
                "cuota_id": instance.cuota_id,
                "seleccion": instance.cuota.seleccion,
                "mercado_id": instance.cuota.mercado_id,
                "evento_id": instance.cuota.mercado.evento_id,
                "valor_anterior": str(instance.valor_anterior),
                "valor_nuevo": str(instance.valor_nuevo),
            },
        )
    except Exception:
        pass


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
