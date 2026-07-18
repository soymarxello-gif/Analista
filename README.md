# Analista

Scanner avanzado para detectar setups **long-only** de swing trading en acciones comunes cotizadas en Estados Unidos.

## Objetivo operativo

- Solo posiciones largas.
- Horizonte operativo: 4 a 21 sesiones.
- Revisión y ejecución manual.
- Sin construcción automática de cartera.
- Yahoo/yfinance como fuente principal.
- Finviz, MarketWatch y TradingView como fuentes secundarias cuando corresponda.

## Universo

Se permiten:

- Acciones comunes listadas en bolsas estadounidenses.
- ADRs líquidos.
- Emisores extranjeros líquidos cotizados en Estados Unidos.

Se excluyen:

- ETF y ETN.
- Closed-end funds.
- Preferred shares.
- Warrants, rights y units.
- Mutual funds.
- SPACs pre-deal.
- ADRs ilíquidos.

Filtros duros actuales:

```yaml
min_price: 10
min_market_cap_usd: 1500000000
```

Toda violación de filtro duro fuerza `signal = VETO` y debe quedar registrada en `all_veto_reasons`.

## Arquitectura lógica

```text
Yahoo/yfinance screener
→ validación de universo
→ metadata/fundamentales
→ revalidación post-metadata
→ precios OHLCV
→ indicadores técnicos
→ liquidez
→ régimen de mercado
→ rotación sectorial
→ fuerza relativa
→ setups
→ riesgo/beneficio ATR
→ opciones put/call
→ scoring
→ clasificación de señal
→ CSV/JSON/Markdown/HTML
→ auditoría de salud del scan
```

## Señales habilitadas

| Señal | Lectura | Operable |
|---|---|---:|
| `VETO` | Falla filtro duro o setup inválido | No |
| `AVOID` | Activo elegible, pero riesgo o setup débil | No |
| `WATCHLIST` | Interesante, pero incompleto | No |
| `READY_WAIT_TRIGGER` | Setup válido, esperando confirmación | No |
| `TRIGGER_CONFIRMED` | Trigger confirmado y sujeto a revisión manual | Revisión manual |

`BUY_SETUP_ACTIVE` permanece deshabilitado hasta completar validaciones adicionales.

Reglas semánticas:

```text
READY_WAIT_TRIGGER  => trigger_confirmed == false
TRIGGER_CONFIRMED   => trigger_confirmed == true
TRIGGER_CONFIRMED   => execution_quote_quality != LOW
TRIGGER_CONFIRMED   => rr >= 2.0
NO_VALID_SETUP      => signal = VETO
```

## Calidad de cotización

Campos obligatorios:

```text
quote_status
execution_quote_quality
```

Valores permitidos:

```text
quote_status:
- VALID
- INVALID
- STALE_POSSIBLE
- MISSING
- WIDE_OR_INCOHERENT

execution_quote_quality:
- HIGH
- MEDIUM
- LOW
```

Una cotización con calidad `LOW` no puede producir `TRIGGER_CONFIRMED`. Si el trigger técnico existe, la señal se degrada a `WATCHLIST` y se registra `execution_quote_unconfirmed`.

## Niveles operativos y teóricos

Para filas `VETO`:

```text
actionable_entry  = null
actionable_stop   = null
actionable_target = null
```

Los niveles de investigación deben almacenarse en:

```text
theoretical_entry
theoretical_stop
theoretical_target
```

## Scores

El modelo separa:

```text
asset_quality_score
setup_quality_score
context_score
institutional_score
final_trade_score
```

El principio operativo es que un activo puede ser de alta calidad sin ofrecer una entrada válida. `NO_VALID_SETUP` fuerza `VETO` y limita `final_trade_score`.

El ranking principal todavía no se ha migrado de forma definitiva. La Fase 9 compara el ranking legacy por `final_score` contra el ranking operativo por `final_trade_score` antes de cambiar el orden productivo.

## Opciones / flujo institucional

Las opciones son un factor confirmatorio, no un filtro duro salvo condiciones extremas de crowded trade.

Clasificación actual:

```text
BULLISH_WITH_DATA
BEARISH_WITH_DATA
NEUTRAL_WITH_DATA
CROWDED_BULLISH
CROWDED_BEARISH
UNKNOWN_OPTIONS_FLOW
```

La ausencia de datos se expresa como `UNKNOWN_OPTIONS_FLOW`; no se interpreta como neutralidad confirmada.

## Perfil de riesgo

Perfil actual: agresivo.

```text
< 0.60 ATR     => AVOID salvo override manual
0.60–1.00 ATR  => permitido con setup fuerte y penalización
1.00–2.50 ATR  => rango preferido
> 2.50 ATR     => penalización por stop amplio
```

## Reportes

```text
CSV completo        auditoría y debugging
JSON completo       integración
Markdown/HTML       revisión manual diaria
```

Campos de auditoría relevantes:

```text
all_veto_reasons
penalty_reasons
score_breakdown
quote_status
execution_quote_quality
missing_critical_fields
missing_important_fields
recommendation
```

## Estado de validación

La Fase 8 quedó aceptada con estado `WARN`, no por falla lógica sino por calidad de datos:

```text
Rows: 355
VETO: 293
WATCHLIST: 37
AVOID: 23
TRIGGER_CONFIRMED: 2
Veto rate: 82.54%
```

Warnings observados:

```text
data_quality LOW elevado: 54.37%
campos críticos faltantes: 54.37%
bid/ask inválido o stale: 83.38%
```

No debe relajarse la validación de cotizaciones para reducir estos warnings, porque eso reintroduciría señales operativas basadas en quotes defectuosos.

## Fase actual

La siguiente etapa es **Fase 9 — auditoría de ranking**:

```text
legacy_rank_basis = final_score
trade_rank_basis  = final_trade_score
rank_delta        = diferencia entre ambos
```

El ranking principal solo debe cambiar si:

1. Los tests P0 siguen limpios.
2. `final_trade_score` prioriza mejor setups válidos.
3. `NO_VALID_SETUP` no asciende al top.
4. Los `VETO` no suben por calidad general del activo.
5. `TRIGGER_CONFIRMED` y `WATCHLIST` con setup válido mejoran su prioridad.

Consulta `docs/PHASE_9_RANKING_AUDIT.md` para el procedimiento de implementación y aceptación.

## Instalación

```powershell
cd "C:\Users\El otro Yo\Projects\ChatGPT\Analista"
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecución

```powershell
python run_scanner.py --verbose
```

Con límite de candidatos:

```powershell
python run_scanner.py --max-candidates 300 --verbose
```

## Dashboard

```powershell
streamlit run ui/dashboard.py
```

## Validación local

```powershell
python tools/validate_project.py
python -m compileall .
pytest
ruff check .
```

## Limpieza

No subir:

```text
.venv/
cache/
logs/
reports/
__pycache__/
```

## Limitaciones

- El screener usa canales predefinidos de yfinance.
- Las métricas de opciones son heurísticas y no representan gamma exposure real.
- El R:R todavía no modela resistencias mediante perfil de volumen completo.
- La calidad de bid/ask de Yahoo puede ser insuficiente para una parte importante del universo.
- No ejecuta órdenes ni reemplaza la validación manual.

## Advertencia

Este software es una herramienta analítica. No ejecuta órdenes, no constituye asesoría financiera y requiere revisión manual.
