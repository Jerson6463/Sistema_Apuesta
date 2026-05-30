# ADR-0009: Auditoría Inmutable con Encadenamiento SHA256

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

Los registros de auditoría deben ser a prueba de manipulación. Un administrador malintencionado no debe poder modificar un registro sin que sea detectable.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| Tabla normal con `updated_at` | Simple | Modificable sin detección |
| Firma digital por registro | Muy segura | Requiere PKI; complejidad alta |
| **Encadenamiento de hash SHA256** | Tamper-evident; simple de implementar y verificar | No criptográficamente firmado (un atacante con acceso a DB podría recalcular toda la cadena) |

## Decisión

**Encadenamiento SHA256**: `hash_n = SHA256(hash_n-1 + JSON(payload_n, sort_keys=True))`. El primer registro usa `hash_anterior = "0"*64` (génesis). Un endpoint de verificación recorre toda la cadena y detecta cualquier modificación de payload.

La tabla `RegistroAuditoria` es **append-only** en el admin (sin permisos de change/delete).

## Consecuencias

- **Más fácil:** verificar integridad en O(n) con un endpoint REST de admin.
- **Más difícil:** un atacante con acceso completo a PostgreSQL podría recalcular toda la cadena; para esto se requeriría firmar con clave privada externa.
- **Deuda técnica v2:** exportar hash de la cadena a un servicio externo (timestamping) para prueba forense.
