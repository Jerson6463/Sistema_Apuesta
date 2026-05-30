# ADR-0005: Máquina de Estados de Apuesta con django-fsm

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

Una `Apuesta` pasa por varios estados (aceptada → ganada/perdida/anulada/cash_out). Sin control de transiciones, es posible liquidar dos veces o hacer cash-out de una apuesta ya ganada.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| Campo CharField libre | Simple | Sin validación de transiciones; errores silenciosos |
| django-fsm | Declarativo, protegido, transitions explícitas | Dependencia extra |
| Implementación manual | Control total | Código repetitivo y propenso a bugs |

## Decisión

**django-fsm** con `FSMField(protected=True)`. Las transiciones se declaran con `@transition` y django-fsm levanta `TransitionNotAllowed` si se intenta una transición inválida. El campo `protected=True` impide asignación directa.

## Estados y transiciones:
```
aceptada → ganada      (liquidar_apuesta: selección == resultado)
aceptada → perdida     (liquidar_apuesta: selección != resultado)
aceptada → anulada     (anular_apuesta: evento anulado)
aceptada → cash_out    (hacer_cash_out: usuario solicita cierre anticipado)
```

## Consecuencias

- **Más fácil:** tests de estados son claros; imposible liquidar dos veces (FSM protegido).
- **Más difícil:** cambios de estado siempre deben pasar por el método de transición.
- **Deuda técnica:** documentar en diagrama de estados (ver /docs/sketches/).
