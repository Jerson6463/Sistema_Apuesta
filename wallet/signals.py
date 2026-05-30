from django.db.models.signals import post_save
from django.dispatch import receiver

from wallet.models import EntradaContable


@receiver(post_save, sender=EntradaContable)
def registrar_movimiento_en_auditoria(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from audit.services import registrar_evento
        from audit.models import TipoEventoAuditoria
        registrar_evento(
            tipo=TipoEventoAuditoria.WALLET,
            payload={
                "entrada_id": str(instance.id),
                "cuenta": instance.cuenta,
                "direccion": instance.direccion,
                "monto": str(instance.monto),
                "tipo_referencia": instance.tipo_referencia,
                "id_transaccion": str(instance.id_transaccion),
                "referencia_id": str(instance.referencia_id) if instance.referencia_id else None,
            },
            usuario=instance.usuario,
        )
    except Exception:
        pass
