# ADR-0002: Manejo de Decimal y Precisión Financiera

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

Los montos monetarios (fichas) deben calcularse sin errores de redondeo. Python `float` es binario y produce errores acumulativos (ej. `0.1 + 0.2 != 0.3`).

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| `float` | Simple, rápido | Imprecisión binaria, ilegal en sistemas financieros |
| `int` (centavos) | Preciso, simple de operar | Requiere conversión constante, difícil de leer |
| `Decimal` (Python) | Precisión exacta, estándar contable | Algo más lento que float |

## Decisión

**`Decimal` con `max_digits=18, decimal_places=4`** en todos los campos monetarios. Está explícitamente prohibido usar `float` en cualquier monto. Los cálculos de payout usan `stake * odds` directamente en Decimal sin conversión intermedia.

## Consecuencias

- **Más fácil:** tests de precisión exacta con `assertEqual`, invariante de payout verificable.
- **Más difícil:** cuidado con operaciones que devuelvan `float` (e.g. librerías externas).
- **Regla:** cualquier valor que entre al sistema vía API se parsea como `Decimal` en el serializer antes de usarse.
