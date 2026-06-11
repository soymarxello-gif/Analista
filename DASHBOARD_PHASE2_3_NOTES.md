# Integración opcional en ui/dashboard.py

Agregar estas columnas a vistas principales:

```python
"operational_priority_score",
"operational_priority_bucket",
"quality_composite_score",
"operational_priority_warning",
"source_quality_score",
"source_channels",
"screener_hit_count",
"screener_weighted_hits",
```

Esto permite ordenar visualmente por prioridad operativa.
