# Declaración de uso de IA — FairBet Lab

**Integrante:** KellyCubas  
**Fecha:** 2026-05-29

---

## Política del equipo

Usamos IA como apoyo al aprendizaje, no como reemplazo del criterio propio. Todo código entregado es comprendido y puede defenderse línea por línea.

---

## Detalle de uso por área

| Área | Uso de IA | Tipo de uso |
|---|---|---|
| Conceptos de partida doble | Claude explicó la diferencia entre saldo almacenado y calculado | Estudiar concepto |
| `select_for_update` | Consulté documentación de Django sobre bloqueo pesimista | Estudiar concepto |
| `django-fsm` | IA explicó cómo funciona `protected=True` y `@transition` | Estudiar concepto |
| Algoritmo SHA256 encadenado | Claude explicó el concepto de blockchain-lite para auditoría | Estudiar concepto |
| Django Channels | Consulté ejemplos de `AsyncWebsocketConsumer` para entender el protocolo | Estudiar concepto |
| Hypothesis | IA explicó cómo funciona property-based testing con ejemplos | Estudiar concepto |
| Boilerplate de serializers DRF | Generación del scaffold inicial de serializers | Generar boilerplate [ai-assisted] |
| Estructura inicial de docker-compose | Generación del docker-compose base | Generar boilerplate [ai-assisted] |

---

## Lo que NO fue generado por IA

- La lógica de negocio de `recargar_fichas`, `bloquear_fondos_apuesta`, `liberar_fondos_ganancia`
- Las transiciones FSM de `Apuesta` y `Evento`
- El algoritmo de encadenamiento de hash en `audit/services.py`
- Los tests de invariantes financieras (TDD)
- Los tests de concurrencia con `threading`
- Las decisiones documentadas en los ADRs

---

## Compromiso

Todo código en este repositorio que lleve mi nombre como autor puede ser explicado y modificado en vivo durante el walkthrough.
