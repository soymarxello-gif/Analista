# Analista

Scanner MVP avanzado para detectar setups **long-only** de swing trading en acciones comunes estadounidenses.

## Reglas operativas

- Solo acciones comunes USA.
- Solo posiciones largas.
- Horizonte operativo: 4 a 21 días.
- ETFs excluidos como activos operables.
- ETFs/índices solo como benchmarks de mercado.
- Yahoo/yfinance como fuente principal.
- Opciones se usan solo como confirmación de flujo, no como activo operable.

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
→ scoring final
→ clasificación de señal
→ CSV/JSON/dashboard
```

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

Reporte específico con opciones:

```powershell
python run_scanner.py --max-candidates 30 --verbose --csv-out reports/latest_scan_options.csv --json-out reports/latest_scan_options.json
```

## Dashboard

```powershell
streamlit run ui/dashboard.py
```

El dashboard permite seleccionar CSVs desde:

```text
reports/*.csv
reports/history/*.csv
```

## Señales

| Señal | Lectura |
|---|---|
| `BUY_SETUP_ACTIVE` | Setup confirmado, score alto y R:R suficiente |
| `READY_WAIT_TRIGGER` | Buen candidato, falta confirmación |
| `WATCHLIST` | Interesante, pero incompleto |
| `AVOID` | Score o estructura débil |
| `VETO` | Falla crítica de liquidez, tendencia, R:R, setup o earnings cercano |

## Opciones / Put-Call Flow

Columnas principales:

| Columna | Descripción |
|---|---|
| `options_score` | Score 0–1 de confirmación por opciones |
| `options_bias` | `BULLISH`, `NEUTRAL`, `BEARISH`, `NEUTRAL_NO_DATA` |
| `options_confidence` | Confianza según liquidez de opciones |
| `put_call_volume_ratio` | Volumen puts / calls |
| `put_call_oi_ratio` | Open interest puts / calls |
| `call_volume_share` | Participación de calls en volumen total |
| `near_call_oi_share` | Dominancia de calls cerca del precio |
| `max_call_oi_strike` | Strike con mayor OI de calls |
| `max_put_oi_strike` | Strike con mayor OI de puts |
| `max_pain_approx` | Max pain aproximado |

Regla operativa:

```text
Técnico fuerte + RS fuerte + volumen fuerte + opciones bullish = mayor confianza.
Técnico fuerte + opciones bearish = baja prioridad o watchlist.
Opciones bullish + técnico débil = no compra.
Put/call extremadamente bajo + precio extendido = posible crowded trade.
```

## Validación local

```powershell
python -m compileall .
python tools/validate_project.py
```

## Limpieza recomendada

No subir al repositorio:

```text
.venv/
cache/
logs/
reports/
__pycache__/
```

Estos paths están cubiertos por `.gitignore`.

## Limitaciones actuales

- El screener usa canales predefinidos de yfinance; todavía no usa filtros Yahoo custom avanzados.
- Las métricas de opciones son heurísticas, no cálculo real de gamma exposure.
- El R:R usa ATR y máximos recientes; todavía no modela resistencias por pivotes/volumen.
- El sentimiento contrarian sigue como placeholder neutral.
- No ejecuta órdenes ni reemplaza validación manual.

## Advertencia

Este software es una herramienta analítica. No ejecuta órdenes, no constituye asesoría financiera y requiere validación manual.
