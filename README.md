# Analista

> El motor institucional point-in-time y su estado de implementación están documentados en
> [`docs/INSTITUTIONAL_ARCHITECTURE.md`](docs/INSTITUTIONAL_ARCHITECTURE.md) y
> [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md). La matriz de pruebas está en
> [`docs/VALIDATION_1.81.0.md`](docs/VALIDATION_1.81.0.md).

Scanner avanzado para detectar setups **long-only** de swing trading en acciones y ETF cotizados en Estados Unidos.

## Estado funcional

Versión `1.81.0`. El backend institucional es el único flujo productivo. Android funciona como cliente de revisión; el motor Yahoo local solo puede ejecutarse con una opción legacy explícita y nunca actúa como fallback.

## Reglas operativas

- Solo posiciones largas.
- Horizonte: 4 a 21 sesiones.
- Revisión y ejecución manual.
- Sin construcción automática de cartera.
- Fuente operativa: store institucional point-in-time.
- Acciones: security master Nasdaq Trader/Alpaca y datos SIP cuando están disponibles.
- Fundamentales e insiders: SEC; macro: FRED/ALFRED; posicionamiento: CFTC/FINRA.
- Opciones: OPRA para uso operativo.
- Yahoo Finance queda limitado al modo legacy de investigación; TradingView no se usa como proveedor de datos.

## Universo

Permitidos: acciones comunes, ETF, ADRs líquidos y emisores extranjeros líquidos cotizados en Estados Unidos.

Excluidos: ETN, closed-end funds, preferred shares, warrants, rights, units, mutual funds, SPACs pre-deal y ADRs ilíquidos.

Filtros duros:

```yaml
min_price: 10
min_market_cap_usd: 1500000000
```

El mínimo de capitalización se aplica a acciones, no a ETF. Una capitalización confirmada bajo el mínimo fuerza `VETO`; si el dato no está disponible, el símbolo continúa con la advertencia `stock_market_cap_unavailable`.

## Pipeline

```text
Nasdaq Trader + Alpaca Assets + metadata de capitalización declarada
→ ingestión Alpaca SIP point-in-time
→ universo completo elegible, sin top-N
→ discovery RSI6/RSI14 y features técnicas
→ setup y geometría de riesgo
→ selección y ranking exclusivamente técnicos
→ macro, fundamentales y opciones como contexto posterior no eliminatorio
→ lifecycle de decisión
→ señal inmutable + shadow run + outcomes
→ API autenticada
→ Android para revisión manual
```

## Señales habilitadas

| Señal | Lectura | Operable |
|---|---|---:|
| `HARD_VETO` | Falla crítica o filtro duro confirmado | No |
| `DATA_BLOCKED` | Setup visible, pero falta un dato de grado operativo | No |
| `SETUP_DISCOVERED` | Filtro técnico superado; plan aún incompleto | No |
| `READY_FOR_NEXT_SESSION` | Setup y riesgo válidos con mercado cerrado | No |
| `LIVE_TRIGGER_PENDING` | Sesión abierta; trigger aún no confirmado | No |
| `TRIGGER_CONFIRMED` | Trigger confirmado, quote aceptable y R:R suficiente | Revisión manual |

El cierre del mercado no elimina un setup. La ausencia de macro, fundamentales u opciones se muestra como advertencia y no modifica el score, ranking, estado ni elegibilidad del candidato.

Reglas:

```text
READY_FOR_NEXT_SESSION => market_session_open == false
LIVE_TRIGGER_PENDING   => market_session_open == true && trigger_confirmed == false
TRIGGER_CONFIRMED  => trigger_confirmed == true
DATA_BLOCKED       => required_data_status in {UNAVAILABLE, STALE, ERROR}
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

`setup_quality` es una puntuación de investigación separada de `data_confidence`, `regime_risk` y `execution_readiness`. Se marca explícitamente `UNCALIBRATED_RESEARCH_SCORE`: no es una probabilidad.

`final_score` y `final_trade_score` se calculan solo con componentes técnicos disponibles. `context_score`, `institutional_score` y `fundamental_score` son evidencia descriptiva y nunca participan en selección o ranking.

Cuando no hay contexto, el valor permanece ausente y se muestra una advertencia explícita; no se imputa neutralidad ni se rebaja la señal.

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

Las opciones respaldan o advierten sobre un setup ya seleccionado. La ausencia se reporta como `UNKNOWN_OPTIONS_FLOW` y `Sin datos de opciones`, sin modificar score, ranking o señal.

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
$env:APCA_API_KEY_ID="..."
$env:APCA_API_SECRET_KEY="..."
$env:APCA_DATA_FEED="sip"
python run_scanner.py --ingest-live --json-out reports/latest_scan.json
```

Servicio para Android:

```powershell
$env:ANALISTA_API_TOKEN="token-largo-y-aleatorio"
uvicorn institutional.api:app --host 0.0.0.0 --port 8000
```

El acceso desde un teléfono debe publicarse detrás de HTTPS. El modo legacy se conserva exclusivamente para comparación: `python run_scanner.py --engine legacy`.

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

- SIP y OPRA requieren la suscripción correspondiente; IEX nunca confirma RVOL ni triggers.
- Nasdaq Screener se rotula como metadata de capitalización de investigación; puede sustituirse por `ANALISTA_MARKET_CAP_FILE`.
- Las métricas de opciones no se presentan como gamma real sin OPRA/modelo validado.
- La capa auditada no sustituye revisión manual.
- El ranking productivo no cambia hasta validar varias corridas.
- No ejecuta órdenes.

## Advertencia

Herramienta analítica para revisión manual. No constituye asesoría financiera.
