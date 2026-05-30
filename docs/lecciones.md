# Lecciones aprendidas — FairBet Lab

## Sprint 1 — Wallet y Partida Doble

### Intento fallido 1: usar saldo como columna en la tabla Usuario
Implementé inicialmente un campo `saldo = DecimalField` en el modelo `Usuario`. Al ejecutar las primeras pruebas de concurrencia, dos requests simultáneas leían el mismo saldo y ambas aprobaban la apuesta, generando saldo negativo. **Solución:** eliminar el campo y calcular siempre con `SUM(creditos) - SUM(debitos)`.

### Intento fallido 2: usar float para montos
Intenté usar `float` en los cálculos de payout para simplificar. El test `0.1 + 0.2 == 0.3` falló inmediatamente (`False`). **Solución:** migrar todos los campos a `Decimal(max_digits=18, decimal_places=4)` y prohibir `float` en cualquier cálculo monetario.

### Intento fallido 3: select_for_update fuera de atomic()
Apliqué `select_for_update()` sin envolver en `@transaction.atomic`. Django levantó `TransactionManagementError`. **Solución:** siempre combinar `select_for_update()` dentro de `atomic()` o decorar el servicio con `@transaction.atomic`.

### Intento fallido 4: idempotencia solo en el servicio, no en la DB
Verifiqué idempotencia solo en código Python (`if ya_existe: return`). Bajo condición de carrera, dos requests llegaban simultáneamente antes de que ninguna insertara, ambas pasaban el check. **Solución:** agregar `UniqueConstraint(fields=["id_transaccion", "cuenta", "direccion"])` a nivel DB como segunda capa de protección.

---

## Sprint 2 — Máquina de Estados y Auditoría

### Intento fallido 5: cambiar estado de Apuesta con asignación directa
Asigné `apuesta.estado = "ganada"` sin usar la transición FSM. `django-fsm` levantó `TransitionNotAllowed` porque el campo es `protected=True`. **Solución:** usar siempre los métodos de transición (`apuesta.marcar_ganada()`).

### Intento fallido 6: auditoría con UPDATE en lugar de INSERT
Intenté actualizar el registro de auditoría al liquidar una apuesta en lugar de crear uno nuevo. Eso rompe la cadena de hash. **Solución:** la tabla `RegistroAuditoria` es estrictamente append-only; cada cambio de estado genera un nuevo registro encadenado.

### Intento fallido 7: calcular hash sin `sort_keys=True` en JSON
El hash era inconsistente porque el orden de las claves del dict variaba entre ejecuciones. **Solución:** usar `json.dumps(payload, sort_keys=True)` para garantizar determinismo.

### Intento fallido 8: WebSocket sin Redis Channel Layer
Configuré Channels sin definir `CHANNEL_LAYERS`. Los mensajes enviados al grupo no llegaban a ningún consumer. **Solución:** configurar `channels_redis.core.RedisChannelLayer` con la URL de Redis en `settings.py`.
