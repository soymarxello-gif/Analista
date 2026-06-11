# Integración en engine/scanner_engine.py

## 1) Importar

Agregar:

```python
from scoring.operational_priority import calculate_operational_priority
```

## 2) Asegurar columnas de fuente en row

Dentro de `row = { ... }`, agregar si aún no están:

```python
"source_channel": m.get("source_channel"),
"source_channels": m.get("source_channels"),
"screener_hit_count": m.get("screener_hit_count"),
"screener_weighted_hits": m.get("screener_weighted_hits"),
"avg_source_rank": m.get("avg_source_rank"),
"best_source_rank": m.get("best_source_rank"),
"source_quality_score": m.get("source_quality_score"),
```

## 3) Calcular prioridad operativa

Después de:

```python
signal, veto = classify_signal(row, config)
row["signal"] = signal
row["veto_reasons"] = ", ".join(veto)
row["reason_summary"] = _reason_summary(row)
```

agregar:

```python
priority = calculate_operational_priority(row, config)
row.update(priority)
```

## 4) Ordenar por prioridad dentro de cada señal

Puedes dejar el orden actual por `signal_order` + `final_score`, o cambiar a:

```python
out = (
    out.sort_values(["_signal_order", "operational_priority_score", "final_score"], ascending=[True, False, False])
    .drop(columns=["_signal_order"])
    .reset_index(drop=True)
)
```

Recomendación: usar `operational_priority_score` para revisión manual, no para cambiar la tesis principal.
