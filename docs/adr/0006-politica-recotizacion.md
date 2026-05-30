# ADR-0006: Política de Re-cotización de Cuotas en Tiempo Real

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

Si las cuotas cambian mientras el usuario tiene el ticket de apuesta abierto, ¿se acepta con la cuota vieja, la nueva, o se requiere reconfirmación?

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| Aceptar con cuota al abrir | Simple para el usuario | La casa puede tener cuotas incorrectas; favorece arbitraje |
| Aceptar con cuota actual | Siempre correcto | El usuario puede recibir una cuota diferente a la que vio |
| **Reconfirmación obligatoria** | Transparente; usuario decide | Un paso extra de UX |

## Decisión

**Reconfirmación obligatoria**: si la cuota cambió entre que el usuario abrió el ticket y confirmó, el WebSocket notifica el cambio y el frontend debe mostrar la nueva cuota y pedir confirmación explícita antes de enviar la apuesta.

El snapshot de la cuota en `Apuesta.cuota_al_apostar` garantiza que el payout siempre se calcule con la cuota acordada, no la actual.

## Consecuencias

- **Más fácil:** sin disputas sobre qué cuota se aplicó; la cuota es inmutable una vez apostada.
- **Más difícil:** UX ligeramente más compleja (modal de reconfirmación).
- **Implementación:** el Consumer WebSocket `CuotasEventoConsumer` emite `aviso: "La cuota cambió. Confirme la nueva cuota para continuar."`.
