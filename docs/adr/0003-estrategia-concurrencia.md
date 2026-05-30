# ADR-0003: Estrategia de Concurrencia — select_for_update vs Optimista

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

Múltiples requests simultáneos de apuesta del mismo usuario podrían causar doble gasto si no se serializa el acceso al saldo.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| **Bloqueo pesimista** (`select_for_update`) | Garantía fuerte, sin reintentos, simple de razonar | Puede generar deadlocks si no se ordena correctamente; bloquea la fila |
| **Bloqueo optimista** (version field) | Sin bloqueos, más escalable | Requiere lógica de reintento; más complejo; riesgo de starvation |
| **Idempotency key única** en DB | Previene duplicados a nivel DB | No evita la condición de carrera; solo evita el doble registro |

## Decisión

**Bloqueo pesimista** (`select_for_update()`) dentro de `atomic()` en todos los servicios de wallet. Se complementa con **idempotency keys** (UUID único por transacción) como segunda capa de defensa.

## Consecuencias

- **Más fácil:** razonar sobre la corrección; los tests de concurrencia son deterministas.
- **Más difícil:** throughput limitado bajo alta carga (mitigable con sharding por usuario).
- **Deuda técnica:** en v2, evaluar bloqueo optimista con reintentos automáticos para escalar horizontalmente.
