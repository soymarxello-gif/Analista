# Integración opcional en engine/scanner_engine.py

## 1) Agregar pre_veto_signal al row

Importar:

```python
from scoring.signal_classifier import classify_signal, classify_base_signal
```

Donde hoy tienes:

```python
signal, veto = classify_signal(row, config)
```

cambiar a:

```python
row["pre_veto_signal"] = classify_base_signal(row, config)

signal, veto = classify_signal(row, config)
row["signal"] = signal
row["veto_reasons"] = ", ".join(veto)
row["reason_summary"] = _reason_summary(row)
```

Esto permite ver:
- qué señal habría tenido el candidato antes de vetos
- por qué quedó bloqueado

## 2) Agregar columnas al dashboard

Agregar `pre_veto_signal` a las vistas principales del dashboard.
