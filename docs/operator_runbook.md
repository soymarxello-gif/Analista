# Analista - Operator Runbook

Este runbook se mantiene como referencia rápida. La documentación principal
vigente está en `docs/OPERATING_MANUAL.md`, `docs/DAILY_WORKFLOW.md`,
`docs/REPORTS_REFERENCE.md`, `docs/SAFETY_RULES.md` y
`docs/CALIBRATION_GUIDE.md`.

## 1. Propósito

Analista es un sistema de apoyo para descubrir oportunidades de swing trading long-only en acciones US-listed.

No ejecuta órdenes.
El sistema no recomienda compras automáticas y no reemplaza la revisión manual del operador.

Uso permitido:

- Revisión manual de candidatos long-only.
- Swing trading con horizonte aproximado de 4 a 21 días.
- Priorización de candidatos según calidad técnica, riesgo, datos y trazabilidad.
- Detección de candidatos que requieren validación live quote.

Uso no permitido:

- Compra automática.
- Venta automática.
- No operar candidatos VETO o AVOID.
- No operar RECHECK_LIVE_QUOTE sin validar precio, spread y gráfico manualmente.
- No usar el ranking como señal de entrada directa.
- No usar quote LOW como confirmación operativa.

---

## 2. Comando diario principal

Ejecutar desde la raíz del proyecto:

python .\tools\daily_validation.py

Activar entorno virtual:

.\.venv\Scripts\Activate.ps1

---

## 3. Archivos que se deben abrir primero

Después de correr daily_validation.py, revisar en este orden:

1. reports/daily_operator_index.md
2. reports/daily_quality_gate_latest.md
3. reports/live_quote_recheck_latest.md
4. reports/trade_decision_checklist_latest.md
5. reports/trade_candidate_cards_latest.md
6. reports/simple_candidate_posttest_latest.md
7. reports/macro_event_context_latest.md
8. reports/manual_review_top.md
9. reports/daily_run_manifest_latest.md
10. reports/release_readiness_latest.md
11. reports/daily_validation_summary.txt
12. reports/project_preflight_latest.md
13. reports/encoding_audit_latest.md
14. reports/latest_scan_audited.csv

La interfaz Streamlit resume estos reportes en un cockpit:

streamlit run .\app.py

Secciones principales:

- Resumen.
- Candidatos.
- Posttest automatico simple.
- Control.

En Candidatos existe `Consulta puntual por ticker` para analizar un ticker con
el motor profundo sin ejecutar el screener completo ni crear señales.

---

## 4. Interpretación de estados

PASS:

La corrida terminó sin errores bloqueantes.

WARN:

La corrida terminó con advertencias. Se permite revisión manual con validación reforzada.

FAIL:

La corrida tiene errores bloqueantes. No usar candidatos operativamente.

---

## 5. Quality gate

El archivo principal de decisión operativa es:

reports/daily_quality_gate_latest.md

Campos clave:

- manual_review_allowed
- manual_review_mode
- issue_count
- fail_issues
- warn_issues

manual_review_allowed = False

No revisar candidatos para operación.

manual_review_mode = BLOCKED

No usar la corrida.

manual_review_mode = REINFORCED

Revisión permitida, pero con validación extra.

manual_review_mode = NORMAL

Revisión manual normal permitida.

---

## 6. Señales operativas

Estados permitidos por el sistema:

- VETO
- AVOID
- WATCHLIST
- READY_WAIT_TRIGGER
- TRIGGER_CONFIRMED

Actualmente BUY_SETUP_ACTIVE está deshabilitado.

VETO no es operable.

AVOID no es operable por ahora.

WATCHLIST es monitoreo, no compra.

READY_WAIT_TRIGGER requiere gatillo validado.

TRIGGER_CONFIRMED requiere revisión manual final.

TRIGGER_CONFIRMED exige quote_status VALID y execution_quote_quality HIGH.

No ejecutar automáticamente.

---

## 7. Reglas para RECHECK_LIVE_QUOTE

RECHECK_LIVE_QUOTE no es entrada.

Significa que el candidato tiene potencial, pero la calidad de quote no permite confirmación operativa automática.

Antes de considerar operación:

1. Validar precio actual en plataforma externa.
2. Validar bid/ask.
3. Validar spread.
4. Confirmar que el precio no esté sobreextendido.
5. Revisar gráfico diario.
6. Revisar intradía solo para afinar entrada.
7. Confirmar stop y target.
8. Confirmar earnings.
9. Confirmar contexto macro.

Si no se puede validar quote, no operar.

---

## 8. Checklist manual antes de operar

Antes de cualquier compra manual:

- daily_quality_gate no está en FAIL.
- daily_validation no está en FAIL.
- project_consistency_audit pasa.
- El candidato no es VETO.
- El candidato no es AVOID.
- Si es RECHECK_LIVE_QUOTE, se validó quote live.
- execution_quote_quality no es LOW sin validación manual.
- El gráfico diario confirma estructura.
- El gráfico semanal no contradice la tesis.
- No hay sobreextensión evidente.
- RSI no está extremo sin corrección.
- R/R es aceptable.
- Stop definido.
- Target definido.
- Earnings revisado.
- Liquidez suficiente.
- Contexto macro revisado.
- Tamaño de posición definido fuera del sistema.

---

## 9. Qué hacer si daily_validation queda FAIL

Abrir:

reports/daily_validation_summary.txt

Buscar la sección Steps.

Corregir el primer step requerido con FAIL.

Luego ejecutar:

python .\tools\daily_validation.py

No usar candidatos hasta que el fallo requerido desaparezca.

---

## 10. Qué hacer si daily_quality_gate queda FAIL

Abrir:

reports/daily_quality_gate_latest.md

Revisar Issues.

Mientras el gate esté en FAIL:

manual_review_allowed = False

manual_review_mode = BLOCKED

No operar.

---

## 11. Qué hacer si release_readiness queda FAIL

Abrir:

reports/release_readiness_latest.md

Revisar Issues y Comandos de validación.

No declarar release listo hasta corregir.

---

## 12. Qué hacer con project_preflight WARN

Abrir:

reports/project_preflight_latest.md

WARN puede ser aceptable si no faltan carpetas requeridas, no faltan scripts requeridos, reports permite escritura, daily_validation no está en FAIL y quality_gate no está en FAIL.

---

## 13. Qué hacer con encoding_audit WARN

Abrir:

reports/encoding_audit_latest.md

Si hay mojibake o caracteres rotos:

- No publicar reportes.
- No copiar reportes a documentación final.
- Corregir encoding antes de compartir.

---

## 14. Qué hacer con reports_cleanup

Abrir:

reports/reports_cleanup_latest.md

Si hay candidatos temporales:

python .\tools\reports_cleanup.py --apply

Este comando mueve archivos temporales a reports/tmp.

No borra archivos.

---

## 15. Flujo operativo recomendado

Paso 1:

python .\tools\daily_validation.py

Paso 2:

Abrir reports/daily_quality_gate_latest.md.

Si está en FAIL, detener.

Paso 3:

Abrir reports/daily_operator_index.md.

Paso 4:

Abrir reports/manual_review_top.md.

Paso 5:

Validar manualmente gráfico diario, gráfico semanal, precio live, spread, volumen, R/R, stop, target, earnings y contexto macro.

Paso 6:

La decisión final de operar se realiza fuera de Analista.

Analista no coloca órdenes.

---

## 16. Comandos de validación profesional

Ejecutar antes de declarar una versión estable:

python -m pytest -q

python .\tools\project_consistency_audit.py

python .\tools\daily_validation.py

python .\tools\release_readiness_check.py

Resultado aceptable:

- pytest PASS.
- project_consistency_audit PASS.
- daily_validation PASS o WARN controlado.
- daily_quality_gate PASS o WARN controlado.
- release_readiness PASS o WARN controlado.

Resultado no aceptable:

- daily_validation FAIL.
- daily_quality_gate FAIL.
- release_readiness FAIL.
- project_consistency_audit FAIL.
- pytest FAIL.

---

## 17. Definición de release MVP v1.0

Analista puede declararse MVP v1.0 si:

- pytest general pasa.
- project_consistency_audit pasa.
- daily_validation no queda en FAIL.
- daily_quality_gate no queda en FAIL.
- release_readiness no queda en FAIL.
- daily_operator_index muestra quality gate.
- manual_review_top existe.
- manual_review_latest existe.
- encoding_audit existe.
- daily_run_manifest existe.
- operator_runbook existe.

---

## 18. Límites del sistema

Limitaciones conocidas:

- Yahoo Finance puede entregar bid/ask stale, inválido o faltante.
- Options flow puede quedar UNKNOWN_OPTIONS_FLOW en gran parte del universo.
- RECHECK_LIVE_QUOTE requiere validación externa.
- Institutional flow avanzado no está completo.
- La UI visual todavía debe construirse.
- El sistema no calcula tamaño de posición definitivo.
- El sistema no reemplaza criterio del operador.

---

## 19. Roadmap posterior

Próximos bloques profesionales:

1. Interfaz visual local.
2. Live quote recheck integrado.
3. Mejor fallback de fuentes.
4. Institutional flow avanzado.
5. Outcome learning y calibración con resultados reales.

---

## 20. Regla final

Si existe conflicto entre ranking y seguridad operativa:

manda la seguridad operativa.

Si existe conflicto entre precio y calidad de datos:

manda la calidad de datos.

Si existe conflicto entre setup y quote no validado:

no operar.
