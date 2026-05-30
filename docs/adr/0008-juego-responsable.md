# ADR-0008: Controles de Juego Responsable como Requisito Funcional Bloqueante

**Fecha:** 2026-05-29  
**Autor:** KellyGoyes

## Contexto

La Ley 31557 y DS 005-2023-MINCETUR exigen controles de juego responsable. Deben ser **bloqueantes**, no solo informativos.

## Decisión y controles implementados

| Control | Implementación | Carácter |
|---|---|---|
| Límite diario de recarga | `_verificar_limite_diario()` en `recargar_fichas()` → `LimiteSuperadoError` | **BLOQUEANTE** |
| Límite semanal y mensual | `LimiteJuego.actualizar_limite()` | Configurable por usuario |
| Cooldown 24h para subir límites | `fecha_ultimo_aumento_*` en `LimiteJuego` | **BLOQUEANTE** |
| Autoexclusión temporal | `AutoExclusion` con `fecha_fin`; bloquea `puede_apostar()` | **BLOQUEANTE** |
| Autoexclusión indefinida | `fecha_fin=None`; irreversible automáticamente | **BLOQUEANTE** |
| Mensaje de consumo responsable | En cada respuesta de `CrearApuestaView` y `CrearApuestaCombinada_View` | **OBLIGATORIO** |
| Footer educativo | Texto fijo en todas las pantallas de apuesta | **OBLIGATORIO** |

## Consecuencias

- **Más fácil:** cumplir la norma; los tests verifican que los controles son realmente bloqueantes.
- **Más difícil:** UX para usuarios que quieren subir sus límites (deben esperar 24h).
- **Límites no cubiertos por esta versión:** historial de pérdidas con alertas automáticas, integración con registro nacional de autoexcluidos (RENAJU).
