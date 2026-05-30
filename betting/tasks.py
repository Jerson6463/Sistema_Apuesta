"""
Tareas Celery para la app betting.

- publicar_actualizacion_cuota: notifica via Channels cuando cambia una cuota
- suspender_mercado_temporalmente: suspende y reactiva un mercado in-play
- liquidar_apuestas_evento: liquida todas las apuestas de un evento finalizado
- detectar_actividad_sospechosa: motor anti-fraude básico
"""
import logging
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def publicar_actualizacion_cuota(self, evento_id: int, cuota_id: int,
                                  seleccion: str, valor_anterior: str,
                                  valor_nuevo: str):
    """
    Publica en el canal Redis del evento para que todos los suscriptores
    WebSocket reciban la nueva cuota.
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    grupo = f"evento_{evento_id}_cuotas"

    try:
        async_to_sync(channel_layer.group_send)(
            grupo,
            {
                "type": "cuota_actualizada",
                "cuota_id": cuota_id,
                "seleccion": seleccion,
                "valor_anterior": valor_anterior,
                "valor_nuevo": valor_nuevo,
            },
        )
    except Exception as exc:
        logger.error("Error publicando cuota en canal %s: %s", grupo, exc)
        raise self.retry(exc=exc, countdown=5)


@shared_task
def suspender_mercado_temporalmente(mercado_id: int, segundos: int = 30):
    """
    Suspende un mercado in-play por N segundos tras un evento crítico
    (gol, expulsión) y luego lo reactiva automáticamente.
    """
    from betting.models import Mercado, EstadoMercado

    try:
        mercado = Mercado.objects.get(pk=mercado_id)
    except Mercado.DoesNotExist:
        return

    if mercado.estado == EstadoMercado.ABIERTO:
        mercado.estado = EstadoMercado.SUSPENDIDO
        mercado.save(update_fields=["estado"])
        logger.info("Mercado %s suspendido por %ds", mercado_id, segundos)

        # Programar reactivación
        reactivar_mercado.apply_async(args=[mercado_id], countdown=segundos)


@shared_task
def reactivar_mercado(mercado_id: int):
    from betting.models import Mercado, EstadoMercado

    try:
        mercado = Mercado.objects.get(pk=mercado_id)
    except Mercado.DoesNotExist:
        return

    if mercado.estado == EstadoMercado.SUSPENDIDO:
        mercado.estado = EstadoMercado.ABIERTO
        mercado.save(update_fields=["estado"])
        logger.info("Mercado %s reactivado", mercado_id)


@shared_task
def liquidar_apuestas_evento(evento_id: int, resultado_ganador: str):
    """
    Liquida todas las apuestas aceptadas de un evento cuando finaliza.
    resultado_ganador: valor de Cuota.seleccion del resultado real.
    """
    from betting.models import Apuesta, EstadoApuesta
    from betting.services import liquidar_apuesta, anular_apuesta

    apuestas = Apuesta.objects.filter(
        cuota__mercado__evento_id=evento_id,
        estado=EstadoApuesta.ACEPTADA,
    ).select_related("cuota", "usuario")

    liquidadas = 0
    errores = 0
    for apuesta in apuestas:
        try:
            liquidar_apuesta(apuesta, resultado_ganador=resultado_ganador)
            liquidadas += 1
        except Exception as e:
            logger.error("Error liquidando apuesta %s: %s", apuesta.id, e)
            errores += 1

    logger.info(
        "Evento %s liquidado: %d apuestas procesadas, %d errores.",
        evento_id, liquidadas, errores,
    )


@shared_task
def detectar_actividad_sospechosa():
    """
    Motor anti-fraude básico: detecta patrones sospechosos y crea alertas.
    Ejecutar periódicamente (ej. cada 15 minutos con Celery Beat).
    """
    from django.db.models import Count
    from django.contrib.auth import get_user_model
    from audit.models import ActividadSospechosa
    from betting.models import Apuesta, EstadoApuesta
    from wallet.models import EntradaContable, TipoReferencia

    Usuario = get_user_model()
    now = timezone.now()
    hace_1h = now - timezone.timedelta(hours=1)

    # Regla 1: Múltiples cuentas desde la misma IP en la última hora
    ips_sospechosas = (
        Apuesta.objects.filter(creado_en__gte=hace_1h, ip_origen__isnull=False)
        .values("ip_origen")
        .annotate(n_usuarios=Count("usuario", distinct=True))
        .filter(n_usuarios__gte=3)
    )
    for entry in ips_sospechosas:
        usuarios_afectados = Apuesta.objects.filter(
            creado_en__gte=hace_1h, ip_origen=entry["ip_origen"]
        ).values_list("usuario", flat=True).distinct()
        for uid in usuarios_afectados:
            usuario = Usuario.objects.get(pk=uid)
            if not ActividadSospechosa.objects.filter(
                usuario=usuario,
                tipo_alerta="multiples_cuentas_ip",
                creado_en__gte=hace_1h,
            ).exists():
                ActividadSospechosa.objects.create(
                    usuario=usuario,
                    tipo_alerta="multiples_cuentas_ip",
                    descripcion=(
                        f"IP {entry['ip_origen']} registró "
                        f"{entry['n_usuarios']} usuarios distintos en 1h."
                    ),
                )

    # Regla 2: Depósito seguido inmediatamente de cash-out (en menos de 10 min)
    hace_10m = now - timezone.timedelta(minutes=10)
    recargas_recientes = EntradaContable.objects.filter(
        tipo_referencia=TipoReferencia.RECARGA,
        creado_en__gte=hace_10m,
    ).values_list("usuario_id", flat=True).distinct()

    for uid in recargas_recientes:
        if uid is None:
            continue
        cashout_inmediato = EntradaContable.objects.filter(
            usuario_id=uid,
            tipo_referencia=TipoReferencia.CASH_OUT,
            creado_en__gte=hace_10m,
        ).exists()
        if cashout_inmediato:
            usuario = Usuario.objects.get(pk=uid)
            if not ActividadSospechosa.objects.filter(
                usuario=usuario,
                tipo_alerta="deposito_cashout_inmediato",
                creado_en__gte=hace_10m,
            ).exists():
                ActividadSospechosa.objects.create(
                    usuario=usuario,
                    tipo_alerta="deposito_cashout_inmediato",
                    descripcion="Recarga seguida de cash-out en menos de 10 minutos.",
                )

    logger.info("Análisis anti-fraude completado.")
