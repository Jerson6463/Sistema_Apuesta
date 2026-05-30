# Bocetos del Sistema — FairBet Lab

Esta carpeta contiene los bocetos a mano requeridos por la guía del challenge.

## Bocetos requeridos

### 1. ER del Wallet (Partida Doble)
**Archivo:** `er_wallet.jpg` (pendiente escanear)

Diagrama entidad-relación que muestra:
- `EntradaContable` con sus campos (id, cuenta, usuario_fk, monto, direccion, id_transaccion, tipo_referencia)
- Relación con `Usuario` (FK)
- Cuentas: `wallet_usuario`, `casa`, `apuestas_pendientes`, `bonos`
- Invariante: toda transaccion tiene suma neta = 0

### 2. Máquina de Estados completa de Bet
**Archivo:** `fsm_apuesta.jpg` (pendiente escanear)

Estados y transiciones:
```
[aceptada] ---(resultado == seleccion)---> [ganada]
[aceptada] ---(resultado != seleccion)---> [perdida]
[aceptada] ---(evento anulado)-----------> [anulada]
[aceptada] ---(usuario solicita)---------> [cash_out]
```
Cada flecha indica el método FSM y el efecto en el wallet.

### 3. Secuencia "Apuesta → Liquidación"
**Archivo:** `secuencia_apuesta_liquidacion.jpg` (pendiente escanear)

Diagrama de secuencia con actores: Usuario, API, WalletService, BettingService, AuditoriaService, DB.

Pasos:
1. Usuario POST /api/apuestas/ con clave_idempotencia
2. API valida usuario, mercado, evento, monto
3. WalletService.bloquear_fondos_apuesta() con select_for_update
4. BettingService crea Apuesta(estado=aceptada)
5. Signal registra en RegistroAuditoria
6. Admin marca resultado → BettingService.liquidar_apuesta()
7. WalletService.liberar_fondos_ganancia/perdida()

### 4. Secuencia "Cash-Out"
**Archivo:** `secuencia_cashout.jpg` (pendiente escanear)

Pasos:
1. Usuario POST /api/apuestas/cash-out/ con apuesta_id
2. API verifica estado=aceptada
3. Calcula: cashout = stake × odds_original / odds_actual × factor_casa
4. WalletService devuelve stake + acredita diferencia si positiva
5. Apuesta pasa a estado cash_out
