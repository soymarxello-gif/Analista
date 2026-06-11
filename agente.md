# AGENTE.md — Analista / Codex

Documento operativo para continuar el proyecto **Analista** en Codex o en cualquier editor asistido por IA.

Este archivo resume la identidad del agente, las reglas maestras, la investigación base, la planificación por fases, el estado actual del proyecto, los comandos de validación y las fases pendientes.

---

## 1. Identidad del agente

Eres un agente de desarrollo para el proyecto **Analista**.

Tu rol es ayudar a construir, auditar y mantener un scanner de **swing trading long-only** para acciones listadas en EE. UU. El sistema está diseñado para descubrir setups de compra manual, no para operar automáticamente.

### Perfil del sistema

```yaml
project:
  name: Analista
  objective: discover_long_swing_setups
  strategy_direction: long_only
  horizon_days:
    min: 4
    max: 21
  portfolio_construction: false
  execution_mode: manual_review
```

### Principios obligatorios

1. No crear ni activar ejecución automática de órdenes.
2. No construir portafolios automáticos.
3. No emitir señales de compra automática.
4. No activar `BUY_SETUP_ACTIVE` hasta que exista una fase explícita para ello.
5. Todo resultado operativo debe pasar por revisión manual.
6. `VETO` y `AVOID` nunca son operables.
7. `WATCHLIST` no es entrada.
8. `RECHECK_LIVE_QUOTE` exige validación de precio/quote antes de considerar operación.
9. `execution_quote_quality = LOW` impide `TRIGGER_CONFIRMED`.
10. Cualquier cambio de lógica de ranking, señales o scoring debe hacerse primero en modo auditado.

---

## 2. Fuentes de datos e investigación base

### Fuente principal

```yaml
data_sources:
  primary: Yahoo Finance / yfinance
```

### Fuentes secundarias, por prioridad

```yaml
fallback_sources:
  - Finviz
  - MarketWatch
  - TradingView_free_data
```

### Regla de uso de fuentes

1. Usar Yahoo Finance como fuente principal.
2. Si Yahoo falla o entrega datos incompletos, declarar el fallo.
3. Pasar a Finviz, luego MarketWatch, luego TradingView gratuito.
4. Si ninguna fuente entrega datos confiables, declarar explícitamente que no hay dato confiable.
5. No inventar quotes, fundamentales, opciones ni datos macro.
6. Mantener trazabilidad por campo cuando sea posible:
   - `price_source`
   - `quote_source`
   - `fundamentals_source`
   - `options_source`

---

## 3. Universo aprobado

```yaml
universe:
  mode: us_listed_common_equities

  allow:
    - stocks_listed_in_us_exchanges
    - liquid_adrs
    - liquid_foreign_issuers_listed_in_us

  exclude:
    - ETF
    - ETN
    - closed_end_fund
    - preferred_share
    - warrant
    - rights
    - unit
    - mutual_fund
    - SPAC_pre_deal
    - illiquid_ADR
```

Se permiten emisores no estadounidenses si cotizan en EE. UU. y cumplen liquidez, estructura y calidad operativa.

Ejemplos aceptables si cumplen filtros:

```text
TSM, ARGX, MT, STX, IX, CRDO
```

---

## 4. Filtros duros obligatorios

Los filtros duros deben ejecutarse **antes del scoring**.

```yaml
hard_filters:
  min_price_usd: 10
  min_market_cap_usd: 1500000000
```

Reglas:

```python
if price < 10:
    signal = "VETO"
    veto_reasons.append("price_below_min")

if market_cap_usd < 1_500_000_000:
    signal = "VETO"
    veto_reasons.append("market_cap_below_min")

if instrument_type in EXCLUDED_INSTRUMENT_TYPES:
    signal = "VETO"
    veto_reasons.append("non_tradable_instrument")
```

Criterio de aceptación:

```text
Ningún ticker bajo USD 10 puede ser WATCHLIST o superior.
Ningún ticker bajo USD 1.5B puede ser WATCHLIST o superior.
Ningún ETF/ETN/fondo/unidad/warrant puede aparecer como candidato operable.
Todo filtro duro violado debe aparecer en all_veto_reasons.
```

---

## 5. Calidad de datos y quotes

### `quote_status`

Valores permitidos:

```yaml
quote_status:
  - VALID
  - INVALID
  - STALE_POSSIBLE
  - MISSING
  - WIDE_OR_INCOHERENT
```

### `execution_quote_quality`

Valores permitidos:

```yaml
execution_quote_quality:
  - HIGH
  - MEDIUM
  - LOW
```

### Reglas

```python
if bid is None or ask is None:
    quote_status = "MISSING"
    execution_quote_quality = "LOW"

elif bid <= 0 or ask <= 0:
    quote_status = "INVALID"
    execution_quote_quality = "LOW"

elif ask <= bid:
    quote_status = "INVALID"
    execution_quote_quality = "LOW"

elif bid_ask_far_from_price:
    quote_status = "STALE_POSSIBLE"
    execution_quote_quality = "LOW"

else:
    quote_status = "VALID"
    execution_quote_quality = "HIGH"
```

### Regla operativa

```python
if execution_quote_quality == "LOW":
    signal cannot be "TRIGGER_CONFIRMED"
    signal cannot be "BUY_SETUP_ACTIVE"
```

Si un setup tiene trigger técnico pero quote de baja calidad:

```python
if execution_quote_quality == "LOW" and signal == "TRIGGER_CONFIRMED":
    signal = "WATCHLIST"
    recommendation = "RECHECK_LIVE_QUOTE"
    penalty_reasons.append("execution_quote_unconfirmed")
```

---

## 6. Estados de señal aprobados

Estados permitidos actualmente:

```yaml
signal_state:
  - VETO
  - AVOID
  - WATCHLIST
  - READY_WAIT_TRIGGER
  - TRIGGER_CONFIRMED
```

`BUY_SETUP_ACTIVE` queda reservado para fase futura.

| Estado | Significado | Operable ahora |
|---|---|---:|
| `VETO` | Falla filtro duro o setup inválido | No |
| `AVOID` | Cumple universo, pero riesgo/setup débil | No |
| `WATCHLIST` | Interesante, pero incompleto | No |
| `READY_WAIT_TRIGGER` | Setup válido, esperando trigger | No |
| `TRIGGER_CONFIRMED` | Trigger confirmado, requiere revisión manual | Solo revisión manual |

Reglas:

```python
if signal == "READY_WAIT_TRIGGER":
    assert trigger_confirmed is False

if signal == "TRIGGER_CONFIRMED":
    assert trigger_confirmed is True
    assert execution_quote_quality != "LOW"
    assert rr >= min_rr
```

---

## 7. Scores y jerarquía conceptual

El sistema separa la calidad del activo de la calidad de la entrada.

```yaml
scores:
  asset_quality_score:
    description: calidad general del activo

  setup_quality_score:
    description: calidad del punto de entrada swing

  context_score:
    description: régimen, sector y benchmark

  institutional_score:
    description: opciones y flujo institucional

  final_trade_score:
    description: score operativo final
```

Principio clave:

```text
Un activo excelente puede no tener entrada válida.
```

Regla:

```python
if setup_type == "NO_VALID_SETUP":
    signal = "VETO"
    final_trade_score = min(final_trade_score, 49)
```

---

## 8. Stops, ATR y R/R

Perfil aprobado: **agresivo**.

Esto permite stops bajo 1 ATR si la estructura y el R/R compensan.

```yaml
risk_profile: aggressive

stop_atr_multiple:
  hard_min: 0.60
  caution_zone_min: 0.60
  preferred_min: 1.00
  preferred_max: 2.50
```

Reglas:

```python
stop_atr_multiple = abs(entry - stop) / atr
```

| Stop ATR | Acción |
|---|---|
| `< 0.60 ATR` | `AVOID`, salvo override manual |
| `0.60–1.00 ATR` | Permitido si setup fuerte |
| `1.00–2.50 ATR` | Ideal |
| `> 2.50 ATR` | Penalizar por stop amplio |

Permitir stop bajo 1 ATR solo si:

```python
if stop_atr_multiple < 1.0:
    allowed_if = (
        rr >= 3.0
        and structure_score >= 0.80
        and setup_quality_score >= 75
        and trigger_confirmed is True
    )
```

Penalizaciones:

```python
if stop_atr_multiple < 0.60:
    signal = "AVOID"
    penalty_reasons.append("stop_too_tight_below_0_6_atr")

elif stop_atr_multiple < 1.0:
    penalty_reasons.append("aggressive_tight_stop")
```

---

## 9. Opciones y flujo institucional

Opciones se usan como **factor confirmatorio**, no filtro duro, excepto en extremos.

Clasificación aprobada:

```yaml
options_bias:
  - BULLISH_WITH_DATA
  - BEARISH_WITH_DATA
  - NEUTRAL_WITH_DATA
  - CROWDED_BULLISH
  - CROWDED_BEARISH
  - UNKNOWN_OPTIONS_FLOW
```

Regla para falta de datos:

```python
if options_data_available is False:
    options_bias = "UNKNOWN_OPTIONS_FLOW"
    options_confidence = "UNKNOWN"
    institutional_score_weight = 0
    confidence_penalty += small_penalty
```

Filtro duro solo en extremo:

```python
if (
    options_bias == "CROWDED_BULLISH"
    and put_call_volume_ratio_extremely_low
    and call_volume_share_extreme
    and atm_iv_elevated
):
    penalty_reasons.append("crowded_bullish_options_risk")
```

No es veto automático; debe ser penalización fuerte o degradación a `WATCHLIST`.

---

## 10. Macro mínima obligatoria

El contexto macro mínimo debe considerar:

```yaml
macro_context:
  indicators:
    - US10Y
    - US30Y
    - VIX
    - DXY
    - WTI
    - Bitcoin

  additional_factors:
    - growth
    - inflation
    - employment
    - Fed calendar
    - NFP
    - CPI
    - earnings_calendar
    - liquidity
    - reverse_repos
    - M2
    - catalysts
```

El régimen de mercado ajusta riesgo sugerido, pero no debe cortar tempranamente el universo de discovery.

---

## 11. Análisis técnico mínimo

Temporalidad principal: `1D`.

Contexto superior: `1W`.

Intradía: solo para afinar entrada manual.

Indicadores y estructuras mínimas:

```yaml
technical_minimum:
  indicators:
    - EMA20
    - EMA50
    - EMA200
    - RSI6
    - RSI14
    - MACD
    - stochastic
    - volume
    - relative_volume
    - ATR

  structures:
    - support_resistance
    - breakout
    - pullback
    - reclaim
    - volatility_contraction
    - divergences
    - volume_confirmation
```

Restricciones:

```text
No recomendar entradas en sobreextensión.
Evitar RSI > 75 sin corrección.
Evitar breakouts sin volumen.
Evitar setups con volumen decreciente.
```

---

## 12. Reportes operativos aprobados

Formatos obligatorios:

```yaml
reports:
  csv:
    purpose: audit_and_debugging
    full_fields: true

  json:
    purpose: integration_with_agent_or_codex
    full_fields: true

  markdown_or_html:
    purpose: daily_manual_review
    include_recommendation: true
```

Columnas operativas importantes:

```yaml
technical:
  - rsi6
  - rsi14
  - rsi6_gt_rsi14
  - ema20
  - ema50
  - ema200
  - price_vs_ema20
  - price_vs_ema50
  - price_vs_ema200
  - weekly_trend

entry_logic:
  - trigger_type
  - entry_logic
  - trigger_confirmed
  - actionable_entry
  - actionable_stop
  - actionable_target
  - theoretical_entry
  - theoretical_stop
  - theoretical_target

risk:
  - atr
  - stop_atr_multiple
  - rr
  - risk_pct
  - reward_pct
  - earnings_risk_status

quality:
  - data_quality_score
  - execution_quote_quality
  - quote_status
  - missing_critical_fields
  - missing_important_fields

explanation:
  - all_veto_reasons
  - penalty_reasons
  - score_breakdown
  - recommendation
```

---

## 13. Tests P0 obligatorios

Estos tests protegen la lógica base.

```python
def test_invalid_bidask_cannot_be_trigger_confirmed(candidate):
    if candidate.execution_quote_quality == "LOW":
        assert candidate.signal not in ["TRIGGER_CONFIRMED", "BUY_SETUP_ACTIVE"]


def test_price_filter_is_hard(candidate):
    if candidate.price < 10:
        assert candidate.signal == "VETO"
        assert "price_below_min" in candidate.all_veto_reasons


def test_market_cap_filter_is_hard(candidate):
    if candidate.market_cap_usd < 1_500_000_000:
        assert candidate.signal == "VETO"
        assert "market_cap_below_min" in candidate.all_veto_reasons


def test_ready_wait_trigger_semantics(candidate):
    if candidate.signal == "READY_WAIT_TRIGGER":
        assert candidate.trigger_confirmed is False


def test_trigger_confirmed_semantics(candidate):
    if candidate.signal == "TRIGGER_CONFIRMED":
        assert candidate.trigger_confirmed is True
        assert candidate.execution_quote_quality != "LOW"
        assert candidate.rr >= 2.0


def test_no_valid_setup_is_veto(candidate):
    if candidate.setup_type == "NO_VALID_SETUP":
        assert candidate.signal == "VETO"
        assert candidate.final_trade_score <= 49


def test_veto_has_no_actionable_levels(candidate):
    if candidate.signal == "VETO":
        assert candidate.actionable_entry is None
        assert candidate.actionable_stop is None
        assert candidate.actionable_target is None


def test_buy_setup_active_disabled(candidate):
    assert candidate.signal != "BUY_SETUP_ACTIVE"
```

---

## 14. Estado histórico de fases

### Fase 0 — Reglas maestras

Estado: cerrada.

Se fijó:

```text
long_only
manual_review
horizonte 4–21 días
sin portfolio construction
BUY_SETUP_ACTIVE desactivado
```

### Fase 1 — Filtros duros

Estado: cerrada.

Se implementaron y auditaron filtros de precio, market cap e instrumentos excluidos.

### Fase 2 — Calidad de datos y quote status

Estado: cerrada.

Se creó separación entre:

```text
quote_status
execution_quote_quality
```

### Fase 3 — Semántica de señales

Estado: cerrada.

Se prohibió `BUY_SETUP_ACTIVE` y se normalizó:

```text
VETO
AVOID
WATCHLIST
READY_WAIT_TRIGGER
TRIGGER_CONFIRMED
```

### Fase 4 — Separación de scores

Estado: cerrada.

Se separó:

```text
asset_quality_score
setup_quality_score
context_score
institutional_score
final_trade_score
```

### Fase 5 — Stops, ATR y R/R

Estado: cerrada.

Se implementó perfil agresivo y clasificación de stop ATR.

### Fase 6 — Opciones y flujo institucional

Estado: cerrada parcialmente.

Existe estructura base. Queda pendiente mejora de profundidad y fallback.

### Fase 7 — Reportes

Estado: cerrada.

CSV, JSON, Markdown/HTML quedaron como formatos válidos.

### Fase 8 — Tests automáticos y health

Estado: cerrada con `WARN` aceptable por calidad de datos.

Interpretación:

```text
WARN por data quality no implica falla lógica.
Yahoo/yfinance puede entregar quotes stale o incompletos.
No relajar quote_status ni execution_quote_quality.
```

### Fase 9 — Ranking auditado

Estado: implementada en lógica auditada / continuar monitoreo.

Objetivo:

```text
Comparar ranking legacy vs final_trade_score sin cambiar ranking destructivamente.
```

### Fases 10–17 — Endurecimiento operativo y reportes

Estado: cerradas.

Incluyen:

```text
source coverage
history archive
manual review enrichment
latest scan health
report consistency
recommendation consistency
```

### Fase 18 — History evolution

Estado: cerrada.

Se agregó evolución histórica de tickers desde reportes archivados.

### Fase 19 — Setup persistence score

Estado: cerrada.

Se agregó score de persistencia auditado, sin alterar ranking principal.

### Fase 20–25 — Reportes operativos y workflow diario

Estado: cerradas.

Incluyen:

```text
manual_review_top
live_quote_recheck
report consistency
README / daily workflow
daily_validation_summary
```

### Fase 26 — Outcome tracking

Estado: cerrada.

Scripts principales:

```text
tools/trade_outcome_tracker.py
tools/open_trade_snapshot.py
```

Funciones:

```text
init
add
add-from-manual-review
close
summary
open trade snapshot
```

### Fase 27 — Outcome analytics

Estado: cerrada.

Script:

```text
tools/trade_outcome_analytics.py
```

Outputs:

```text
reports/trade_outcome_analytics_latest.csv
reports/trade_outcome_analytics_latest.md
```

### Fase 28 — Daily operator index

Estado: cerrada.

Script:

```text
tools/daily_operator_index.py
```

Output:

```text
reports/daily_operator_index.md
```

### Fase 29 — Reports cleanup

Estado: cerrada.

Subfases:

```text
29A — reports_cleanup.py limpieza segura
29B — reports_cleanup integrado en daily_validation como DRY_RUN
29C — cleanup status visible en daily_operator_index.md
```

Regla:

```text
DRY_RUN por defecto.
No mover ni borrar automáticamente.
--apply solo manual.
```

### Fase 30 — Project preflight

Estado: cerrada.

Subfases:

```text
30A — project_preflight.py
30B — project_preflight integrado al inicio de daily_validation
30C — project_preflight visible en daily_operator_index.md
```

Outputs:

```text
reports/project_preflight_latest.json
reports/project_preflight_latest.md
```

### Fase 31 — Daily run manifest

Estado actual:

```text
31A — daily_run_manifest.py: cerrada
31B — integración en daily_validation.py: en implementación / pendiente de validar si no se ejecutaron tests
31C — mostrar daily_run_manifest en daily_operator_index.md: pendiente
```

Outputs de 31A:

```text
reports/daily_run_manifest_latest.json
reports/daily_run_manifest_latest.md
```

---

## 15. Flujo diario actual

Comando principal:

```powershell
python .\tools\daily_validation.py
```

Secuencia esperada:

```text
1. project_preflight
2. run_scanner_audited
3. validate_latest_scan_p0
4. latest_scan_health
5. project_consistency_audit
6. source_coverage_audit
7. history_evolution
8. setup_persistence
9. manual_review / manual_review_top
10. open_trade_snapshot
11. trade_outcome_analytics
12. reports_cleanup en DRY_RUN
13. daily_validation_summary
14. daily_operator_index
15. daily_run_manifest, desde Fase 31B
16. daily_validation_summary reescrito con outputs finales
```

Abrir primero:

```text
reports/daily_operator_index.md
reports/daily_validation_summary.txt
reports/manual_review_top.md
reports/manual_review_latest.md
reports/project_preflight_latest.md
reports/daily_run_manifest_latest.md
reports/reports_cleanup_latest.md
```

---

## 16. Comandos de validación global

Ejecutar desde la raíz del proyecto:

```powershell
python -m py_compile .\tools\daily_validation.py
python -m py_compile .\tools\daily_operator_index.py
python -m py_compile .\tools\project_preflight.py
python -m py_compile .\tools\reports_cleanup.py
python -m py_compile .\tools\daily_run_manifest.py
python -m pytest -q
python .\tools\daily_validation.py
```

Revisar:

```powershell
Get-Content .\reports\daily_operator_index.md | Select-Object -First 340
Get-Content .\reports\daily_validation_summary.txt | Select-Object -First 850
Get-Content .\reports\daily_run_manifest_latest.md | Select-Object -First 340
```

---

## 17. Fases pendientes recomendadas

### Fase 31B — Integrar daily run manifest en daily validation

Estado: pendiente de cerrar si no está validada.

Objetivo:

```text
daily_run_manifest debe correr como POST_SUMMARY_STEP después de daily_operator_index.
```

Reglas:

```text
required = False
timeout_seconds = 60
no debe estar en DEFAULT_STEPS
no debe ejecutar scanner
no debe mover ni borrar archivos
```

Validación:

```powershell
python -m py_compile .\tools\daily_validation.py
python -m pytest .\tests\test_daily_validation_phase31b.py -q
python -m pytest .\tests\test_daily_run_manifest_phase31a.py -q
python -m pytest -q
python .\tools\daily_validation.py
```

Cierre:

```text
daily_run_manifest_latest.json generado automáticamente
daily_run_manifest_latest.md generado automáticamente
daily_validation_summary muestra daily_run_manifest
```

---

### Fase 31C — Mostrar manifest en daily_operator_index

Objetivo:

```text
Agregar sección Daily run manifest al índice operativo.
```

Sección esperada:

```text
## Daily run manifest

- status: PASS/WARN/FAIL
- daily_validation: PASS/WARN/FAIL
- project_preflight: PASS/WARN/FAIL
- reports_cleanup: PASS/WARN/FAIL
- git_dirty: True/False
- missing_script_files: N
- missing_report_files: N
```

Reglas:

```text
Si falta daily_run_manifest_latest.json, no debe fallar.
Si manifest está WARN, mostrar advertencia.
Si manifest está FAIL, bloquear operativamente.
No tocar scanner ni ranking.
```

---

### Fase 32A — Higiene Git / repo estable

Objetivo:

```text
Dejar el repo en estado limpio y trazable.
```

Tareas:

```text
1. Revisar git status.
2. Decidir qué archivos versionar.
3. Agregar a .gitignore caches, reportes temporales, .venv y zips.
4. Evitar que cache/fundamentals ensucie cada corrida.
5. Hacer commit estable del MVP.
```

No tocar lógica de trading.

---

### Fase 33A — Data quality fallback

Objetivo:

```text
Reducir WARN por calidad de datos y mejorar confianza de quotes/metadata.
```

Tareas:

```text
1. Mejorar live quote recheck.
2. Agregar fallback a Finviz / MarketWatch / TradingView.
3. Separar metadata cacheada vs metadata fresca.
4. Reintentar solo tickers operables, no todo el universo.
5. Marcar fuente usada por campo.
```

Regla:

```text
No relajar quote_status ni execution_quote_quality.
Corregir fuente, no relajar riesgo.
```

---

### Fase 34A — Mejorar opciones / flujo institucional

Objetivo:

```text
Usar opciones solo en candidatos prioritarios y mejorar lectura institucional.
```

Tareas:

```text
1. Priorizar opciones para top manual review.
2. Cache TTL específico para opciones.
3. Put/call ratio total y cercano al spot.
4. Open interest por strike cercano.
5. Max pain aproximado.
6. Gamma proxy básico.
7. Separar sin datos vs ilíquido vs fuente falló.
```

---

### Fase 35A — Trade decision checklist

Objetivo:

Crear:

```text
reports/trade_decision_checklist_latest.md
```

Para cada candidato top:

```text
- ticker
- setup
- entry
- stop
- target
- R/R
- quote_status
- execution_quote_quality
- earnings
- ATR risk
- motivo para operar
- motivo para no operar
- checklist final: PASS / RECHECK / AVOID
```

Regla:

```text
No generar orden de compra.
Solo checklist para revisión manual.
```

---

### Fase 36 — Calibración con trades reales

No ejecutar hasta tener muestra mínima.

Mínimo:

```text
20 operaciones cerradas
```

Ideal:

```text
50+ operaciones cerradas
```

Objetivo:

```text
1. Medir setups por resultado real.
2. Calibrar final_trade_score.
3. Calibrar setup_persistence_score.
4. Detectar stops demasiado agresivos.
5. Detectar señales que anticipan pérdidas.
```

---

### Fase 37 — README operativo final

Crear:

```text
README_OPERATIVO.md
```

Debe explicar:

```text
1. Cómo correr el flujo diario.
2. Qué archivo abrir primero.
3. Qué significa PASS/WARN/FAIL.
4. Qué hacer con RECHECK_LIVE_QUOTE.
5. Cómo registrar una operación.
6. Cómo cerrar una operación.
7. Cómo limpiar reportes temporales.
8. Cómo interpretar manifest/preflight/cleanup.
```

---

## 18. Backlog futuro no urgente

```text
- Macro dashboard.
- Sector breadth.
- Relative strength por industria.
- Anchored VWAP / volume profile si hay datos confiables.
- Calendar de earnings ampliado.
- Insider buying/selling.
- ETF/flow institutional si se habilita otra fuente.
- Integración IBKR API solo lectura, no ejecución.
- Export de candidatos a TradingView/Webull watchlist.
```

---

## 19. Reglas para Codex antes de modificar código

Antes de editar:

```text
1. Leer este AGENTE.md.
2. Leer daily_validation.py.
3. Leer daily_operator_index.py.
4. Leer project_preflight.py.
5. Leer daily_run_manifest.py.
6. Leer tests existentes de la fase correspondiente.
7. No modificar scanner_engine.py salvo que la fase lo pida explícitamente.
8. No modificar scoring salvo que la fase lo pida explícitamente.
9. No cambiar nombres de columnas existentes sin migración y tests.
10. No eliminar compatibilidad con tests previos.
```

Después de editar:

```powershell
python -m py_compile <archivo_modificado>
python -m pytest <test_de_fase> -q
python -m pytest -q
```

Si falla un test antiguo:

```text
No borrar el test.
Corregir compatibilidad o explicar explícitamente por qué el cambio de contrato es intencional.
```

---

## 20. Regla de seguridad final

Este proyecto es un sistema de descubrimiento y revisión manual de setups.

Nunca debe transformarse en:

```text
- bot automático de trading
- sistema de órdenes automáticas
- recomendador directo de compra sin validación manual
- portfolio allocator automático
```

El output final correcto es:

```text
candidatos priorizados + evidencia + riesgos + checklist manual
```

No es:

```text
compra ahora
```

---

## 21. Próximo paso recomendado

Si Fase 31B aún no fue validada:

```text
Cerrar Fase 31B.
```

Si Fase 31B ya fue validada:

```text
Avanzar a Fase 31C — mostrar daily_run_manifest en daily_operator_index.md.
```

Luego:

```text
Fase 32A — higiene Git y repo estable.
```
