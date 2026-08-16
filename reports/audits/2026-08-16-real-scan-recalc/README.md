# Auditoría de scans reales y recálculo `backtest-fill-3`

Fecha de corte: 2026-08-16  
Fuente de precios futuros: Yahoo Finance vía `yfinance`  
Motores: `backtest-fill-3`, `walk-forward-statistics-1`, `ranking-promotion-1`

## Alcance

Se tomó una muestra estratificada de cinco scans inmutables de producción: 2026-07-23, 2026-07-28, 2026-07-30, 2026-08-04 y 2026-08-13. Se auditaron las 2.466 filas completas de esos runs y se tomaron las primeras 100 filas por ranking de producción de cada scan para el recálculo de outcomes (500 filas muestreadas).

El schema desktop histórico no almacenaba `maximumEntry`. Para no inventar un chase allowance, el adaptador usa el `entry` persistido como trigger y sólo permite como máximo efectivo los 5 bps de slippage de entrada obligatorios de `backtest-fill-3`. Se excluye la barra diaria del mismo día del scan para evitar look-ahead intradía.

## Calidad de scans reales

| Run | Fecha | Filas | Muestra | TRIGGER_CONFIRMED | Trust | Fuente esencial CRITICAL |
|---|---|---:|---:|---:|---|---|
| 20260723T153344068192Z | 2026-07-23 | 402 | 100 | 3 | UNUSABLE | price_history_yahoo |
| 20260728T154332907566Z | 2026-07-28 | 587 | 100 | 2 | UNUSABLE | price_history_yahoo |
| 20260730T152954356054Z | 2026-07-30 | 530 | 100 | 3 | UNUSABLE | price_history_yahoo |
| 20260804T154628297689Z | 2026-08-04 | 543 | 100 | 3 | UNUSABLE | price_history_yahoo |
| 20260813T144009963304Z | 2026-08-13 | 404 | 100 | 4 | UNUSABLE | price_history_yahoo |

Totales sobre las 2.466 filas auditadas:

- `VETO`: 2.068 (83,86%)
- `WATCHLIST`: 180 (7,30%)
- `AVOID`: 203 (8,23%)
- `TRIGGER_CONFIRMED`: 15 (0,61%)
- execution quote quality `LOW`: 1.718 (69,67%)
- execution quote quality `HIGH`: 731 (29,64%)
- execution quote quality `MEDIUM`: 17 (0,69%)
- `validation_status=PASS`: 565 (22,91%)
- `validation_status=UNKNOWN`: 1.901 (77,09%)
- niveles teóricos completos: 1.691 (68,57%)

### Por qué los runs son `UNUSABLE`

Los cinco runs preservan su clasificación histórica P0 y no se reetiquetan retroactivamente. La telemetría muestra que `price_history_yahoo` obtuvo cobertura 100% y 0 fallos en los cinco casos, pero fue marcado `CRITICAL` por `very_high_latency`:

| Fecha | Items history | Cobertura | Fallos | Latencia total |
|---|---:|---:|---:|---:|
| 2026-07-23 | 293 | 100% | 0 | 18,59 s |
| 2026-07-28 | 476 | 100% | 0 | 26,25 s |
| 2026-07-30 | 413 | 100% | 0 | 22,07 s |
| 2026-08-04 | 422 | 100% | 0 | 40,82 s |
| 2026-08-13 | 297 | 100% | 0 | 16,55 s |

El run del 2026-07-30 también registró `options_yahoo` con 0/3 items cubiertos y `very_low_coverage`. Eso es una degradación institucional adicional, aunque `price_history_yahoo` ya era suficiente para bloquear P0 como fuente esencial.

## Recálculo `backtest-fill-3`

Yahoo entregó barras futuras para 15/15 tickers requeridos (100%). Los 500 candidatos muestreados contienen 15 contratos diagnósticos (`TRIGGER_CONFIRMED`; no había `READY_WAIT_TRIGGER` en esos runs).

Estado al corte 2026-08-16:

- contratos diagnósticos: 15
- activados: 8
- cerrados con retorno realizado: 2
- no activados: 7
- abiertos: 5
- cerrados ambiguos intrabar: 1
- cierres por stop: 2

Los únicos retornos realizados son:

| Run | Ticker | Setup | Entrada | Salida | Motivo | Retorno R |
|---|---|---|---:|---:|---|---:|
| 20260723T153344068192Z | VIST | PULLBACK | 69,68 | 65,93 | STOP | -1,01R |
| 20260804T154628297689Z | AVGO | RECLAIM | 416,03 | 390,15 | STOP | -1,01R |

Existe además un cierre `AMBIGUOUS_ENTRY_STOP_SAME_BAR` en GRND. De acuerdo con `backtest-fill-3`, no se asigna retorno R ni MFE/MAE cuando el orden OHLC intrabar no permite saber si el stop ocurrió antes o después del trigger.

Las métricas agregadas realizadas (`expectancy=-1,01R`, hit rate 0%, drawdown 2,02R) **no son una estimación válida del edge**, porque se basan únicamente en dos cierres y todos los runs son P0 `UNUSABLE`. Cinco contratos activados siguen abiertos y siete no han activado; además ninguno de los runs ha acumulado todavía una ventana completa de 20 sesiones para todos sus contratos.

## Walk-forward

Resultado: **FAIL**.

Partición cronológica 60/20/20:

- training: 9 contratos; 6 activados; 2 cierres; expectancy realizada -1,01R
- validation: 3 contratos; 1 activado; 0 cierres
- test OOS: 3 contratos; 1 activado; 0 cierres

Razones del gate:

1. `insufficient_out_of_sample_closed`: 0 cierres OOS frente al mínimo de 100.
2. `p0_regression_present`: los contratos provienen de runs `UNUSABLE`.
3. `no_dominant_setup_in_test`: no existe muestra cerrada suficiente por setup.
4. `insufficient_market_regimes`: no hay cierres OOS en al menos dos regímenes.

Por tanto, el walk-forward fue recalculado, pero **no es elegible para validar ni promover el sistema**.

## Ranking promotion

Resultado: **KEEP_LEGACY_ORDER**.

- top-K: 5 por run
- selecciones legacy: 25; cierres 2; expectancy -1,01R
- selecciones proposed: 25; cierres 2; expectancy -1,01R
- mejora de expectancy: 0,00R frente al mínimo requerido de +0,10R
- selecciones P0 inválidas proposed: 25/25

Razones:

- `walk_forward_gate_failed`
- `insufficient_legacy_closed_sample`
- `insufficient_proposed_closed_sample`
- `proposed_ranking_selects_invalid_candidates`
- `expectancy_improvement_below_threshold`

No existe base estadística para promover el ranking nuevo.

## Conclusiones de auditoría

1. La corrección `backtest-fill-3` funciona sobre scans reales y no vuelve a introducir el sesgo de expiración ni el sesgo de excursión de la barra de entrada.
2. La fuente Yahoo usada para el recálculo tuvo cobertura 15/15. El problema P0 de los scans históricos no fue pérdida de history, sino la política de latencia de una fuente esencial.
3. La calidad ejecutable de la muestra sigue siendo débil: 69,67% de las filas tienen quote quality `LOW` y sólo 22,91% tienen `validation_status=PASS`.
4. Hay sólo 15 señales `TRIGGER_CONFIRMED` entre 2.466 filas (0,61%). Esa selectividad no es un defecto por sí misma, pero todavía no genera tamaño muestral suficiente para medir edge.
5. Los dos únicos cierres realizados fueron stops. Esto es información negativa temprana, pero con n=2 no permite inferir expectancy futura.
6. Walk-forward y promoción de ranking deben permanecer bloqueados.
7. No se deben calibrar pesos, thresholds ni ranking con estos outcomes mientras no exista muestra P0 válida y suficiente.

## Recomendación arquitectónica derivada

Sin modificar el contrato histórico P0, conviene evaluar una separación explícita entre `execution_trust` y `research_backtest_trust`. Una descarga history completa, timestamped y sin fallos puede ser demasiado lenta para una decisión ejecutable y, a la vez, seguir siendo utilizable para investigación histórica. Esta propuesta es una mejora futura de trazabilidad; **no se utilizó para convertir los runs actuales en válidos**.
