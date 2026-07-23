# Validación de Analista 1.79.0

Fecha de ejecución: 21 de julio de 2026.

## Resultado

| Control | Resultado | Evidencia |
|---|---|---|
| Suite Python | PASS | 63 pruebas (`pytest -q`) |
| Contratos institucionales | PASS | Store point-in-time, discovery y lifecycle |
| Lint Python completo | PASS | Ruff `E,F,I` sobre todo el repositorio |
| Higiene del repositorio | PASS | Sin caches, logs, reportes, ZIP ni parches obsoletos versionados |
| Integridad del diff | PASS | `git diff --check` |
| Validadores heredados | PASS | 15 validadores de schema, temporalidad, fuentes, filtros, mercado, backtest y paridad |
| API local | PASS | Salud 200, endpoint sin token 401 y endpoint autenticado 200 |
| Sintaxis Kotlin modificada | PASS | 21 archivos analizados, cero nodos de error |
| Gradle Wrapper | PASS | Gradle 8.11.1 con SHA-256 de distribución fijado |
| Unit tests Android | PASS | 244 pruebas, cero fallos y cero omitidas |
| Android lint | PASS | Cero errores; 14 advertencias no bloqueantes registradas |
| Ensamblado Android | PASS | APK debug generado y verificado por SHA-256 |

## Comandos reproducibles

```bash
python -m pytest -q
python tools/validate_institutional_engine.py
python tools/validate_repository_hygiene.py
ruff check .
git diff --check

cd android
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug --no-daemon
```

## Límites de la evidencia

- Los tests verifican contratos, temporalidad, estados, ausencia de truncamiento previo, resultados fuera del universo vigente y reglas de promoción.
- Android lint informa 14 advertencias no bloqueantes; no se contabilizan como errores ni como validaciones omitidas.
- No demuestran alfa ni rentabilidad futura.
- La fase shadow está implementada con configuración inmutable y registro append-only, pero su ventana real de 4–8 semanas debe acumularse con sesiones de mercado. Ningún resultado se promociona antes de superar los mínimos OOS definidos.
