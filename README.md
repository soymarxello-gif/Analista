# Analista

Scanner avanzado para detectar setups **long-only** de swing trading en acciones comunes cotizadas en Estados Unidos.

## Estado funcional

Versión auditada `0.2.0`. La salida del motor se normaliza antes de generar reportes para garantizar filtros duros, semántica de señales, calidad de cotización, niveles accionables y auditoría de ranking.

## Reglas operativas

- Solo posiciones largas.
- Horizonte: 4 a 21 sesiones.
- Revisión y ejecución manual.
- Sin construcción automática de cartera.
- Fuente principal: Yahoo Finance/yfinance.
- Fuentes secundarias previstas: Finviz, MarketWatch y TradingView.

## Universo

Permitidos: acciones comunes listadas en Estados Unidos, ADRs líquidos y emisores extranjeros líquidos cotizados en Estados Unidos.

Excluidos: ETF, ETN, closed-end funds, preferred shares, warrants, rights, units, mutual funds, SPACs pre-deal y ADRs ilíquidos.

Filtros duros:

```yaml
min_price: 10
min_market_cap_usd: 1500000000
```

Toda violación fuerza `VETO` y se acumula en `all_veto_reasons`.

## Pipeline

```text
screener
→ validación de universo
→ metadata/fundamentales
→ revalidación
→ OHLCV e indicadores
→ liquidez
→ régimen y sector
→ fuerza relativa
→ setups y R:R
→ opciones
→ scoring legacy
→ normalización auditada
→ scoring operativo y auditoría de ranking
→ CSV/JSON/dashboard
```

La normalización auditada vive en `engine/audit_postprocessor.py`.

## Señales habilitadas

| Señal | Lectura | Operable |
|---|---|---:|
| `VETO` | Falla crítica, filtro duro o setup inválido | No |
| `AVOID` | Riesgo o estructura débil | No |
| `WATCHLIST` | Interesante, pero incompleto | No |
| `READY_WAIT_TRIGGER` | Setup válido sin trigger confirmado | No |
| `TRIGGER_CONFIRMED` | Trigger confirmado, quote aceptable y R:R suficiente | Revisión manual |

`BUY_SETUP_ACTIVE` está deshabilitado y no puede emitirse.

Reglas:

```text
READY_WAIT_TRIGGER => trigger_confirmed == false
TRIGGER_CONFIRMED  => trigger_confirmed == true
TRIGGER_CONFIRMED  => execution_quote_quality != LOW
TRIGGER_CONFIRMED  => rr >= 2.0
NO_VALID_SETUP     => VETO
```

## Calidad de cotización

`quote_status`:

```text
VALID
INVALID
STALE_POSSIBLE
MISSING
WIDE_OR_INCOHERENT
```

`execution_quote_quality`:

```text
HIGH
MEDIUM
LOW
```

Quotes faltantes, inválidos, incoherentes, demasiado amplios o alejados del último precio quedan en calidad `LOW`. No pueden sostener `TRIGGER_CONFIRMED`.

## Niveles operativos

Para `VETO`:

```text
actionable_entry  = null
actionable_stop   = null
actionable_target = null
```

Los niveles de investigación se conservan como:

```text
theoretical_entry
theoretical_stop
theoretical_target
```

## Scores

```text
asset_quality_score
setup_quality_score
context_score
institutional_score
final_trade_score
score_breakdown
```

`NO_VALID_SETUP` limita `final_trade_score` a 49.

Cuando no hay datos de opciones, `institutional_score` queda sin valor y su peso se redistribuye entre los componentes disponibles; no se interpreta la ausencia como neutralidad confirmada.

## Opciones

Estados:

```text
BULLISH_WITH_DATA
BEARISH_WITH_DATA
NEUTRAL_WITH_DATA
CROWDED_BULLISH
CROWDED_BEARISH
UNKNOWN_OPTIONS_FLOW
```

Las opciones funcionan como confirmación. La ausencia de datos se reporta como `UNKNOWN_OPTIONS_FLOW` con confianza `UNKNOWN`.

## Auditoría de ranking

Campos:

```text
legacy_rank
trade_rank
rank_delta
legacy_rank_basis = final_score
trade_rank_basis  = final_trade_score
```

Por seguridad, `ranking_audit.change_production_ranking` permanece en `false`. El orden productivo conserva prioridad por señal y `final_score`, mientras se compara el ranking alternativo.

Consulta `docs/PHASE_9_RANKING_AUDIT.md`.

## Perfil de riesgo

Perfil agresivo:

```text
< 0.60 ATR     => AVOID salvo override manual
0.60–1.00 ATR  => permitido con penalización y setup fuerte
1.00–2.50 ATR  => preferido
> 2.50 ATR     => penalización por stop amplio
```

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Ejecución

```powershell
python run_scanner.py --verbose
```

Con límite:

```powershell
python run_scanner.py --max-candidates 300 --verbose
```

Dashboard:

```powershell
streamlit run ui/dashboard.py
```

## Validación

```powershell
python tools/validate_project.py
python -m compileall .
pytest
ruff check .
```

Los tests P0 cubren filtros duros, quotes inválidos, semántica de señales, `NO_VALID_SETUP`, niveles accionables, desactivación de `BUY_SETUP_ACTIVE`, opciones desconocidas y ranking auditado.

## Limitaciones

- Las cotizaciones bid/ask de Yahoo pueden ser incompletas o stale.
- Las métricas de opciones son heurísticas; no representan gamma exposure real.
- La capa auditada no sustituye revisión manual.
- El ranking productivo no cambia hasta validar varias corridas.
- No ejecuta órdenes.

## Advertencia

Herramienta analítica para revisión manual. No constituye asesoría financiera.
