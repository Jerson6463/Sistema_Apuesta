# ADR-0010: Umbrales del Motor Anti-Fraude

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

El sistema debe detectar actividad sospechosa sin generar demasiados falsos positivos que bloqueen usuarios legítimos.

## Decisión y umbrales elegidos

| Regla | Umbral | Justificación |
|---|---|---|
| Múltiples cuentas por IP | ≥ 3 cuentas distintas desde la misma IP en 1 hora | IP compartida (oficina, VPN) es normal hasta 2; 3+ indica automatización |
| Depósito + cash-out inmediato | Recarga seguida de cash-out en < 10 minutos | Tiempo razonable para que un usuario legítimo apueste y gane |
| Patrón de apuestas idénticas | No implementado en v1 | Requiere análisis de grupos; se documenta como deuda técnica |

## Consecuencias

- **Más fácil:** los falsos positivos son bajos con estos umbrales conservadores.
- **Más difícil:** el fraude organizado con IPs rotativas no se detecta con este modelo simple.
- **Deuda técnica:** implementar análisis de grafos de usuarios conectados por IP/dispositivo en v2.
- **Calibración:** los umbrales deben ajustarse con datos reales después del lanzamiento.
