# Analista — Daily Workflow

## 1. Objetivo del flujo diario

Analista es un scanner de swing trading long-only para acciones US-listed.

El objetivo diario no es comprar automáticamente, sino descubrir candidatos para revisión manual con horizonte operativo aproximado de 4 a 21 días.

Reglas base:

* Solo posiciones largas.
* No hay portfolio construction automática.
* No se opera fuera de horario regular.
* No se compra solo porque aparece una señal.
* Toda entrada requiere revisión manual.
* `BUY_SETUP_ACTIVE` sigue deshabilitado.
* `VETO` y `AVOID` no son operables.
* `RECHECK_LIVE_QUOTE` requiere validar quote antes de considerar una operación.

---

## 2. Comando principal diario

Desde PowerShell, con `.venv` activo:

```powershell
python .\tools\daily_validation.py
```

Este comando debe generar o actualizar:

```text
reports/daily_validation_summary.txt
reports/latest_scan_audited.csv
reports/latest_scan_audited.json
reports/manual_review_latest.csv
reports/manual_review_latest.md
reports/manual_review_top.csv
reports/manual_review_top.md
reports/setup_persistence_latest.csv
reports/setup_persistence_latest.md
reports/history_evolution_latest.csv
reports/history_evolution_latest.md
```

---

## 3. Validación rápida después de correr el flujo diario

Revisar primero el resumen:

```powershell
Get-Content .\reports\daily_validation_summary.txt | Select-Object -First 430
```

Confirmar:

```text
Final status: PASS o WARN
P0 validation: PASS
Manual review persistence: PASS
Manual review top: PASS
Report consistency audit: PASS o WARN
```

Un `WARN` puede ser aceptable si viene de calidad de datos o archivos opcionales.
Un `FAIL` requiere revisión antes de usar cualquier candidato.

---

## 4. Reporte principal para revisión manual

Abrir:

```powershell
Get-Content .\reports\manual_review_top.md | Select-Object -First 180
```

Este reporte organiza los candidatos en grupos:

```text
1_ALTA_CALIDAD_OPERATIVA
2_REQUIERE_RECHECK_QUOTE
3_PERSISTENTE_NO_ACCIONABLE_TODAVIA
4_DETERIORADO_O_DEBIL
```

---

## 5. Interpretación de grupos

### 1_ALTA_CALIDAD_OPERATIVA

Candidatos prioritarios para revisión manual.

Deben cumplir, en general:

* `quote_status = VALID`
* `execution_quote_quality = HIGH`
* `recommendation = WATCHLIST_MONITOR` o equivalente operativo
* `final_trade_score` alto
* `setup_quality_score` aceptable
* `rr` aceptable
* `setup_persistence_score` suficiente

Acción:

```text
Revisar gráfico manualmente.
Confirmar estructura.
Confirmar entrada, stop y target.
Validar volumen y contexto del mercado.
```

No implica compra automática.

---

### 2_REQUIERE_RECHECK_QUOTE

Candidatos interesantes, pero con quote dudoso.

Pueden tener:

```text
quote_status = INVALID
quote_status = STALE_POSSIBLE
quote_status = MISSING
execution_quote_quality = LOW
recommendation = RECHECK_LIVE_QUOTE
```

Acción:

```powershell
python .\tools\live_quote_recheck.py --max-tickers 10
```

Luego revisar:

```powershell
Get-Content .\reports\live_quote_recheck_latest.md | Select-Object -First 160
```

Solo considerar manualmente los que pasen a:

```text
QUOTE_OK_FOR_MANUAL_REVIEW
```

Los que sigan en:

```text
QUOTE_STILL_UNCONFIRMED
QUOTE_FETCH_FAILED
```

no deben operarse con ese dato.

---

### 3_PERSISTENTE_NO_ACCIONABLE_TODAVIA

Candidatos con cierta persistencia o calidad, pero sin confirmación suficiente.

Acción:

```text
Mantener en observación.
Esperar trigger, pullback, mejora de quote o confirmación de volumen.
No comprar todavía.
```

---

### 4_DETERIORADO_O_DEBIL

Candidatos deteriorados, débiles o penalizados.

Acción:

```text
No priorizar.
No operar.
Solo revisar si hay una razón externa fuerte y confirmación técnica posterior.
```

---

## 6. Revisión de quote live

Comando manual:

```powershell
python .\tools\live_quote_recheck.py --max-tickers 10
```

Revisar:

```powershell
Get-Content .\reports\live_quote_recheck_latest.md | Select-Object -First 160
```

Interpretación:

```text
QUOTE_OK_FOR_MANUAL_REVIEW:
El quote live se ve válido. Puede pasar a revisión manual.

QUOTE_STILL_UNCONFIRMED:
El problema de quote persiste. No operar con ese dato.

QUOTE_FETCH_FAILED:
Yahoo/yfinance no pudo confirmar el quote. No operar con ese dato.
```

Importante:

```text
live_quote_recheck.py no cambia señales, ranking ni recomendaciones.
Solo ayuda a decidir si un candidato puede revisarse manualmente.
```

---

## 7. Checklist antes de considerar una compra

Antes de comprar cualquier candidato, confirmar manualmente:

```text
1. El ticker no está en VETO ni AVOID.
2. La recomendación no es RECHECK_LIVE_QUOTE sin validación posterior.
3. quote_status es VALID o live_quote_status es VALID.
4. execution_quote_quality es HIGH o live_execution_quote_quality es HIGH.
5. El setup sigue vigente en gráfico diario.
6. La tendencia semanal no contradice gravemente el setup.
7. El precio no está sobreextendido.
8. RSI14 no está en sobreextensión extrema.
9. El volumen confirma o no contradice el movimiento.
10. R/R es aceptable.
11. Stop y target son coherentes con ATR.
12. No hay earnings inmediatos sin decisión consciente de asumir ese riesgo.
13. El contexto de SPY/QQQ/IWM no está claramente en risk-off severo.
14. No hay noticia o gap que invalide el setup.
```

---

## 8. Reglas de descarte automático

Descartar sin revisión profunda:

```text
signal = VETO
signal = AVOID
setup_type = NO_VALID_SETUP
quote_status = INVALID sin recheck válido
quote_status = MISSING sin recheck válido
quote_status = STALE_POSSIBLE sin recheck válido
execution_quote_quality = LOW sin recheck válido
recommendation = RECHECK_LIVE_QUOTE sin QUOTE_OK_FOR_MANUAL_REVIEW
rr menor al mínimo operativo
stop_atr_status demasiado débil o incoherente
```

---

## 9. Orden diario recomendado

### Paso 1 — correr validación

```powershell
python .\tools\daily_validation.py
```

### Paso 2 — revisar resumen

```powershell
Get-Content .\reports\daily_validation_summary.txt | Select-Object -First 430
```

### Paso 3 — revisar top manual

```powershell
Get-Content .\reports\manual_review_top.md | Select-Object -First 180
```

### Paso 4 — revalidar quotes si hay candidatos en grupo 2

```powershell
python .\tools\live_quote_recheck.py --max-tickers 10
```

### Paso 5 — revisar recheck

```powershell
Get-Content .\reports\live_quote_recheck_latest.md | Select-Object -First 160
```

### Paso 6 — abrir gráficos manualmente

Prioridad:

```text
1. TRIGGER_CONFIRMED con quote válido
2. WATCHLIST_MONITOR con alta calidad operativa
3. RECHECK_LIVE_QUOTE solo si pasó a QUOTE_OK_FOR_MANUAL_REVIEW
4. Persistentes no accionables solo para seguimiento
```

---

## 10. Qué guardar si se toma una operación

Registrar manualmente:

```text
ticker
fecha
hora
entry
stop
target
rr
setup_type
signal
recommendation
final_trade_score
setup_quality_score
setup_persistence_score
motivo de entrada
riesgo asumido
resultado posterior
```

Esto será la base para una fase posterior de outcome tracking y calibración.

---

## 11. Interpretación de estados principales

```text
VETO:
No operable. Falla filtro duro o setup inválido.

AVOID:
No operable. Riesgo, estructura o calidad insuficiente.

WATCHLIST:
Interesante, pero no confirmado para entrada inmediata.

READY_WAIT_TRIGGER:
Setup válido, esperando trigger.

TRIGGER_CONFIRMED:
Trigger confirmado, requiere revisión manual final.

RECHECK_LIVE_QUOTE:
El candidato puede ser interesante, pero el quote no es confiable.
Debe pasar por live_quote_recheck antes de ser considerado.
```

---

## 12. Criterio de cierre diario

El flujo diario se considera sano si:

```text
daily_validation.py corre sin error
P0 validation pasa
manual_review_latest.csv existe
manual_review_top.md existe
recommendation no viene vacía
quotes problemáticos quedan separados
VETO/AVOID no aparecen como operables
live quote recheck no altera señales ni ranking
```

Si algo falla, no usar candidatos hasta revisar el error.
