# Cambios requeridos en engine/scanner_engine.py

Este parche agrega módulos nuevos, pero requiere que el scanner integre dos puntos:

## 1) Importar data quality

Agregar junto a imports:

```python
from datetime import datetime, timezone
from data.data_quality import score_data_quality
```

## 2) Revalidar post-metadata en modo estricto

Cambiar:

```python
meta = enrich_metadata(meta, config)
```

por:

```python
meta = enrich_metadata(meta, config)
meta = validate_universe(meta, config, strict_metadata=True)
```

## 3) Agregar timestamp del scan

Antes del loop final:

```python
scan_timestamp = datetime.now(timezone.utc).isoformat()
```

Dentro del row:

```python
"scan_timestamp": scan_timestamp,
```

## 4) Agregar métodos R:R

El nuevo `scoring/risk_reward_score.py` devuelve:

```python
stop_method
target_method
risk_pct
reward_pct
```

Agregar al row:

```python
"stop_method": rr_data.get("stop_method"),
"target_method": rr_data.get("target_method"),
"risk_pct": rr_data.get("risk_pct"),
"reward_pct": rr_data.get("reward_pct"),
```

## 5) Agregar data quality después de crear row y antes de classify_signal

```python
dq = score_data_quality(row, config)
row.update(dq)
row["warnings"] = _join_warnings(row.get("warnings"), dq.get("data_quality_warning"))
```

Con esto el CSV incluirá:
- data_quality_score
- data_quality_confidence
- missing_critical_fields
- missing_important_fields
- data_quality_warning
