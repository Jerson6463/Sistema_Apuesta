# ADR-0001: Modelo de Partida Doble para el Wallet

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

Necesitamos un sistema de contabilidad para fichas virtuales que garantice integridad financiera, trazabilidad completa y prevención de doble gasto, en cumplimiento con los principios de la Ley 31557.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| **Saldo simple** (columna `saldo`) | Simple, rápido de leer | Propenso a race conditions, sin trazabilidad, fácil de manipular |
| **Historial de movimientos** (log) | Trazable | Sin garantía de balance, difícil auditar |
| **Partida doble** (LedgerEntry) | Integridad matemática garantizada, auditable, estándar contable | Más complejo, consultas más pesadas |

## Decisión

Implementar **partida doble** con modelo `EntradaContable`. Toda operación crea exactamente dos entradas balanceadas. El saldo **nunca se almacena**; siempre se calcula como `SUM(creditos) - SUM(debitos)`.

## Consecuencias

- **Más fácil:** auditoría, detección de fraudes contables, demostrar invariantes con tests.
- **Más difícil:** consultas de saldo son más costosas (requieren agregación); necesita índices en `usuario + cuenta + dirección`.
- **Deuda técnica:** para escala alta, se podría materializar el saldo en Redis como caché (pero la fuente de verdad sigue siendo la DB).
