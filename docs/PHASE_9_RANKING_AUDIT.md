# Fase 9 — Auditoría de ranking

## Objetivo

Comparar el ranking legacy basado en `final_score` con el ranking operativo basado en `final_trade_score` sin modificar todavía el orden productivo.

## Campos nuevos de auditoría

```text
legacy_rank
trade_rank
rank_delta
legacy_rank_basis = final_score
trade_rank_basis  = final_trade_score
```

Definición recomendada:

```python
rank_delta = legacy_rank - trade_rank
```

Interpretación:

- `rank_delta > 0`: el ticker mejora con el ranking operativo.
- `rank_delta < 0`: el ticker pierde prioridad.
- `rank_delta == 0`: no cambia.

## Restricciones

Durante esta fase:

```text
- No cambiar el ranking principal.
- No habilitar BUY_SETUP_ACTIVE.
- No relajar quote_status ni execution_quote_quality.
- No permitir que VETO ascienda por asset_quality_score.
- No modificar pesos de scoring junto con la auditoría.
```

## Implementación sugerida

```python
from __future__ import annotations

import pandas as pd


def add_ranking_audit(df: pd.DataFrame) -> pd.DataFrame:
    required = {"final_score", "final_trade_score", "signal", "setup_type"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing ranking audit columns: {sorted(missing)}")

    out = df.copy()

    out["legacy_rank"] = (
        out["final_score"]
        .rank(method="first", ascending=False, na_option="bottom")
        .astype("Int64")
    )

    out["trade_rank"] = (
        out["final_trade_score"]
        .rank(method="first", ascending=False, na_option="bottom")
        .astype("Int64")
    )

    out["rank_delta"] = out["legacy_rank"] - out["trade_rank"]
    out["legacy_rank_basis"] = "final_score"
    out["trade_rank_basis"] = "final_trade_score"

    return out
```

El cálculo anterior es exclusivamente de auditoría. El orden productivo existente debe permanecer intacto.

## Tablas de comparación

Generar en Markdown/HTML:

1. Top 20 por `final_score`.
2. Top 20 por `final_trade_score`.
3. Mayores mejoras por `rank_delta`.
4. Mayores deterioros por `rank_delta`.
5. Tickers que aparecen solo en uno de los dos Top 20.
6. Distribución por señal dentro de cada Top 20.

Columnas mínimas:

```text
legacy_rank
trade_rank
rank_delta
ticker
signal
recommendation
setup_type
final_score
final_trade_score
asset_quality_score
setup_quality_score
quote_status
execution_quote_quality
rr
stop_atr_status
penalty_reasons
```

## Tests obligatorios

```python
def test_ranking_audit_preserves_rows(result, source):
    assert len(result) == len(source)


def test_ranking_audit_does_not_change_signal(result, source):
    assert result["signal"].tolist() == source["signal"].tolist()


def test_veto_cannot_be_promoted_to_actionable(result):
    veto = result[result["signal"] == "VETO"]
    assert veto["actionable_entry"].isna().all()
    assert veto["actionable_stop"].isna().all()
    assert veto["actionable_target"].isna().all()


def test_no_valid_setup_not_in_trade_top20(result):
    top20 = result.nsmallest(20, "trade_rank")
    assert not (top20["setup_type"] == "NO_VALID_SETUP").any()


def test_low_quote_not_trigger_confirmed(result):
    invalid = result[
        (result["execution_quote_quality"] == "LOW")
        & (result["signal"] == "TRIGGER_CONFIRMED")
    ]
    assert invalid.empty


def test_buy_setup_active_remains_disabled(result):
    assert not (result["signal"] == "BUY_SETUP_ACTIVE").any()
```

## Diagnóstico manual

```powershell
python -c "import pandas as pd; df=pd.read_csv('reports/latest_scan_audited.csv'); cols=['rank','ticker','signal','recommendation','setup_type','final_score','final_trade_score','asset_quality_score','setup_quality_score','quote_status','execution_quote_quality','rr','stop_atr_status','penalty_reasons']; print('TOP final_score'); print(df.sort_values('final_score', ascending=False)[cols].head(20).to_string(index=False)); print('\nTOP final_trade_score'); print(df.sort_values('final_trade_score', ascending=False)[cols].head(20).to_string(index=False))"
```

## Criterios de aceptación

La migración del ranking principal solo puede aprobarse cuando:

1. Todos los tests P0 pasan.
2. La auditoría no cambia señales ni niveles operativos.
3. Ningún `NO_VALID_SETUP` aparece en el Top 20 operativo.
4. Ningún `VETO` asciende por `asset_quality_score`.
5. Ningún quote `LOW` aparece como `TRIGGER_CONFIRMED`.
6. Los setups válidos muestran una mejora interpretable de prioridad.
7. La comparación se valida en varias corridas, no en un único scan.

## Decisión posterior

Si se cumplen los criterios, cambiar el orden operativo a:

```text
_signal_order
operational_priority_score
final_trade_score
final_score
```

El cambio debe realizarse en un commit separado para permitir rollback directo.
