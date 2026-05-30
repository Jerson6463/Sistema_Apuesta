# ADR-0007: WebSocket vs SSE para Cuotas en Tiempo Real

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

Las cuotas deben actualizarse en tiempo real en el cliente. El stack ya incluye Django Channels.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| **WebSocket** (Django Channels) | Bidireccional, bajo latencia, stack ya incluido | Mayor complejidad de infraestructura; necesita Redis channel layer |
| **SSE** (Server-Sent Events) | Simple, unidireccional, funciona sobre HTTP/1.1 | No bidireccional; no estándar en DRF |
| **Polling** | Simplísimo | Latencia alta, gasto de recursos innecesario |

## Decisión

**WebSocket con Django Channels + Redis Channel Layer**. La bidirecionalidad es útil para enviar estado inicial al conectar. El stack (Channels + Redis) ya está en el `docker-compose.yml`.

## Consecuencias

- **Más fácil:** notificaciones push instantáneas; el cliente no necesita polling.
- **Más difícil:** requiere ASGI + Daphne/Uvicorn; no funciona detrás de proxies que no soporten WebSocket sin configuración extra.
- **Deuda técnica:** en producción, asegurar que el load balancer (nginx) tenga `proxy_read_timeout` y soporte `Upgrade: websocket`.
