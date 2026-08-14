# Estado de implementación institucional

Referencia: auditoría del 21 de julio de 2026.

## Fases implementadas

| Fase | Implementación | Verificación automatizada |
|---|---|---|
| 0. Baseline | Snapshot SQLite consistente, configuración y manifiesto SHA-256 en `institutional.baseline`. | `test_baseline_bundle_contains_consistent_database_snapshot_and_hashes` |
| 1. Contratos y servicio | Store SQLite point-in-time y API FastAPI autenticada de ingestión, ejecución, estado, universo, señales, outcomes y fuentes. | `validate_institutional_engine.py`; tests de store/API |
| 2. Universo completo | Security master con vigencias, disponibilidad, acciones y ETF; sin top-N antes de discovery. | Test de 126 símbolos sin truncamiento y funnel de exclusiones |
| 3. Discovery | RSI14 25–65, RSI6>RSI14, EMA20/50/200, RVOL, semana calendario y RS mercado/sector. | Tests de RSI, hash y semana de cuatro sesiones |
| 4. Enriquecimiento | Ingestión tardía FRED/ALFRED, SEC y OPRA como evidencia solo consultiva; CFTC, FINRA y Form 4 permanecen no implementados y visibles. | Tests de contexto point-in-time y advertencias `NO_DATA` |
| 5. Decisión | Selección y ranking técnicos; macro, fundamentales, earnings y opciones nunca filtran, penalizan ni bloquean. | Tests de invariancia del score y conflictos contextuales |
| 6. Validación | Outcomes independientes del universo actual, horizontes 5/10/20, costos y walk-forward rodante con embargo/bootstrap. | Tests de ticker fuera del universo, markout y múltiples folds |
| 7. Android/release | Cliente del API institucional, contexto consultivo visible, token cifrado con Keystore y fallback productivo local deshabilitado. | Fuente 1.81.0; CI usa Wrapper, SDK 35, tests, lint y ensamblado |
| 8. Shadow | Configuración bloqueada por hash, append-only JSONL y rechazo de tuning in-place. | Test de drift de configuración |

## Higiene y configuración canónica

- `config.yaml`, README y Android declaran el mismo universo de acciones y ETF y la versión `1.81.0`.
- El contrato de discovery exige RSI14 25–65, RSI6 sobre RSI14 y ausencia de top-N previo al setup.
- Caches, logs, scans y parches históricos no forman parte del código fuente.
- CI ejecuta lint Ruff completo y `validate_repository_hygiene.py` además de la suite funcional.

## Modo operativo

El motor institucional vive en Python y es el único camino productivo. El store se crea por defecto en `cache/institutional.db`. Android bloquea la ejecución si el servicio no está configurado; no recurre a la watchlist megacap.

```bash
export APCA_API_KEY_ID=...
export APCA_API_SECRET_KEY=...
export APCA_DATA_FEED=sip
python run_scanner.py --ingest-live
export ANALISTA_API_TOKEN=...
uvicorn institutional.api:app --host 0.0.0.0 --port 8000
python tools/validate_institutional_engine.py
python tools/export_institutional_baseline.py --database cache/institutional.db
```

## Reglas de promoción

- No se promueve ningún ranking por existir código o pasar unit tests.
- El mínimo inicial es 200 señales OOS cerradas y 40 por celda dominante.
- Expectancy OOS mínima: 0,10R y límite inferior bootstrap 95% sobre cero.
- Cualquier P0, look-ahead, survivorship bias o drift del shadow lock bloquea promoción.
- El periodo shadow exige tiempo real de mercado. El software está habilitado; la evidencia no puede fabricarse anticipadamente.

## Datos que requieren credenciales o licencia

- SIP para volumen consolidado y confirmación de ejecución.
- OPRA o vendor equivalente para opciones de ejecución.
- Vendor de calendario de earnings con histórico de revisiones.
- Histórico point-in-time de símbolos/corporate actions si se requiere profundidad anterior a la primera ingestión local.

Ante su ausencia, el contexto debe mostrar `NO_DATA` o `DEGRADED_RESEARCH_ONLY`; nunca se imputan valores neutrales ni se invalida el setup. `DATA_BLOCKED` queda reservado a datos técnicos u operativos imprescindibles, como barras o quote para confirmar un trigger.
