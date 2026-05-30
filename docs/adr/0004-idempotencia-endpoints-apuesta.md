# ADR-0004: Idempotencia en Endpoints de Apuesta y Wallet

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

Redes inestables pueden causar que el cliente reintente una request que ya fue procesada, duplicando apuestas o recargas.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| Sin idempotencia | Simple | Doble gasto, doble apuesta |
| Idempotency key en header HTTP | Estándar de la industria | Requiere validación de header |
| UUID en body (`clave_idempotencia`) | Simple, parte del contrato de la API | El cliente debe generar el UUID |

## Decisión

**UUID en body** (`clave_idempotencia`): el cliente genera un UUID v4 antes de enviar. El servidor verifica si ya existe una `EntradaContable` o `Apuesta` con ese UUID. Si existe, devuelve el objeto existente sin procesar de nuevo.

A nivel DB, la constraint `UniqueConstraint(fields=["id_transaccion", "cuenta", "direccion"])` en `EntradaContable` garantiza idempotencia incluso bajo concurrencia.

## Consecuencias

- **Más fácil:** reintentos seguros; el frontend puede reintentar sin riesgo.
- **Más difícil:** el cliente debe generar y persistir el UUID antes de enviar.
- **Regla:** si `clave_idempotencia` no se envía, el servidor genera uno (comportamiento permisivo para dev).
