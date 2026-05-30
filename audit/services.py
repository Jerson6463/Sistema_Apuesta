"""
Servicios de auditoría inmutable.
hash_n = SHA256(hash_n-1 + JSON(payload_n, sort_keys=True))
El primer registro usa hash_anterior = '0' * 64 (génesis).
"""
import hashlib
import json
from typing import Any

from django.db import transaction

from audit.models import RegistroAuditoria, TipoEventoAuditoria

HASH_GENESIS = "0" * 64


def _calcular_hash(hash_anterior: str, payload: dict) -> str:
    datos = hash_anterior + json.dumps(payload, sort_keys=True)
    return hashlib.sha256(datos.encode()).hexdigest()


def _obtener_ultimo_hash() -> str:
    ultimo = RegistroAuditoria.objects.order_by("-creado_en").first()
    return ultimo.hash_actual if ultimo else HASH_GENESIS


@transaction.atomic
def registrar_evento(
    *,
    tipo: str,
    payload: dict[str, Any],
    usuario=None,
) -> RegistroAuditoria:
    """Crea un nuevo registro encadenado al anterior. Siempre dentro de atomic()."""
    # select_for_update para serializar inserciones concurrentes
    ultimo = (
        RegistroAuditoria.objects.select_for_update()
        .order_by("-creado_en")
        .first()
    )
    hash_anterior = ultimo.hash_actual if ultimo else HASH_GENESIS
    hash_actual = _calcular_hash(hash_anterior, payload)

    return RegistroAuditoria.objects.create(
        tipo_evento=tipo,
        payload=payload,
        hash_anterior=hash_anterior,
        hash_actual=hash_actual,
        usuario=usuario,
    )


def verificar_integridad_cadena() -> tuple[bool, list[str]]:
    """
    Recorre todos los registros en orden y verifica que cada hash sea válido.
    Retorna (True, []) si la cadena está íntegra, (False, [errores]) si no.
    """
    registros = list(RegistroAuditoria.objects.order_by("creado_en"))
    errores = []
    hash_esperado_anterior = HASH_GENESIS

    for reg in registros:
        if reg.hash_anterior != hash_esperado_anterior:
            errores.append(
                f"Registro {reg.id}: hash_anterior no coincide. "
                f"Esperado={hash_esperado_anterior[:12]}…, "
                f"Encontrado={reg.hash_anterior[:12]}…"
            )
        hash_recalculado = _calcular_hash(reg.hash_anterior, reg.payload)
        if reg.hash_actual != hash_recalculado:
            errores.append(
                f"Registro {reg.id}: hash_actual no coincide con payload. "
                f"El registro fue manipulado."
            )
        hash_esperado_anterior = reg.hash_actual

    return (len(errores) == 0, errores)
