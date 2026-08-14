# Validación de Analista 1.80.0

Fecha: 21 de julio de 2026.

## Corrección causal

El motor institucional dejó de ser infraestructura paralela. `run_scanner.py`, el endpoint `POST /v1/runs`, el botón Android y el servicio programado recorren ahora la misma ruta:

`ingestión → store point-in-time → universo completo → discovery → decisión → señal → shadow`.

No existe fallback productivo a Yahoo ni a una lista megacap. Un store vacío devuelve `DATA_BLOCKED_EMPTY_UNIVERSE`; un fallo de refresh del API devuelve HTTP 503 y prohíbe servir datos antiguos como ejecución actual.

## Evidencia ejecutada

| Control | Resultado |
|---|---:|
| Suite Python | 67/67 PASS |
| Validadores de contratos/higiene | 18/18 PASS |
| Ruff E/F/I | PASS |
| Compilación/contratos Python | PASS |
| Replay end-to-end determinista | PASS; 3/3 señales persistidas |
| Ingestión determinista | PASS; 2 instrumentos, 480 barras SIP y 9 observaciones tardías FRED/SEC/OPRA |
| Store vacío sin fallback | PASS; `DATA_BLOCKED_EMPTY_UNIVERSE` |
| Entrada productiva y shadow run | PASS |
| Kotlin/Android fuente 1.80.0 | PASS; `compileDebugKotlin` |
| `git diff --check` | PASS |

La compilación Kotlin se ejecutó con JDK 17, Gradle 8.11.1, AGP 8.9.1 y dependencias reales del proyecto. El SDK 35 completo no persistió en este sandbox; por ello no se volvió a contabilizar `assembleDebug`, lint ni las 244 pruebas Android como una nueva ejecución. Esos controles permanecen obligatorios en CI con `android-actions/setup-android`.

## Límites honestos

- No se dispuso de credenciales Alpaca dentro de este entorno para una corrida SIP de mercado real.
- Nasdaq Screener es metadata de capitalización de investigación, identificada como tal; `ANALISTA_MARKET_CAP_FILE` permite reemplazarla.
- El score de setup se rotula `UNCALIBRATED_RESEARCH_SCORE`; no representa probabilidad ni alfa demostrado.
- La promoción institucional continúa condicionada a SIP/OPRA reales y al shadow/OOS predeclarado.
