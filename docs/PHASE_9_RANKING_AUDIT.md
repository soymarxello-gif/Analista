# Fase 9 — Auditoría de ranking

## Estado

Implementada en modo no destructivo mediante `engine/audit_postprocessor.py`.

```yaml
ranking_audit:
  enabled: true
  change_production_ranking: false
  legacy_basis: final_score
  trade_basis: final_trade_score
```

El ranking productivo todavía no migra. La salida conserva prioridad por señal y `final_score`, pero incluye la comparación completa contra `final_trade_score`.

## Campos

```text
legacy_rank
trade_rank
rank_delta
legacy_rank_basis
trade_rank_basis
```

Definición:

```python
rank_delta = legacy_rank - trade_rank
```

- Positivo: mejora con el ranking operativo.
- Negativo: pierde prioridad.
- Cero: no cambia.

## Componentes operativos

```text
asset_quality_score
setup_quality_score
context_score
institutional_score
final_trade_score
score_breakdown
```

Pesos actuales:

```yaml
asset_quality: 0.25
setup_quality: 0.40
context: 0.25
institutional: 0.10
```

Cuando no existen datos de opciones, `institutional_score` queda vacío y su peso no participa; los pesos disponibles se normalizan. Esto evita convertir ausencia de información en neutralidad confirmada.

`NO_VALID_SETUP` limita `final_trade_score` a 49 y fuerza `VETO`.

## Controles preservados

- `BUY_SETUP_ACTIVE` no puede emitirse.
- Quotes `LOW` no pueden ser `TRIGGER_CONFIRMED`.
- `READY_WAIT_TRIGGER` requiere trigger falso.
- `TRIGGER_CONFIRMED` requiere trigger verdadero, quote aceptable y R:R mínimo 2.0.
- Precio inferior a USD 10 fuerza `VETO`.
- Capitalización inferior a USD 1.5B fuerza `VETO`.
- Instrumentos no elegibles fuerzan `VETO`.
- Filas `VETO` no exponen niveles accionables.
- Los motivos se acumulan en `all_veto_reasons`.

## Tablas de comparación recomendadas

1. Top 20 por `final_score`.
2. Top 20 por `final_trade_score`.
3. Mayores mejoras por `rank_delta`.
4. Mayores deterioros por `rank_delta`.
5. Tickers exclusivos de cada Top 20.
6. Distribución de señales en ambos rankings.

Columnas mínimas:

```text
legacy_rank
trade_rank
rank_delta
ticker
signal
setup_type
final_score
final_trade_score
asset_quality_score
setup_quality_score
quote_status
execution_quote_quality
rr
penalty_reasons
```

## Diagnóstico manual

```powershell
python -c "import pandas as pd; df=pd.read_csv('reports/latest_scan.csv'); cols=['legacy_rank','trade_rank','rank_delta','ticker','signal','setup_type','final_score','final_trade_score','asset_quality_score','setup_quality_score','quote_status','execution_quote_quality','rr','penalty_reasons']; print('TOP LEGACY'); print(df.sort_values('legacy_rank')[cols].head(20).to_string(index=False)); print('\nTOP TRADE'); print(df.sort_values('trade_rank')[cols].head(20).to_string(index=False))"
```

## Tests

`tests/test_audit_postprocessor.py` valida:

- quote inválido no puede confirmar trigger;
- filtros duros de precio y capitalización;
- semántica de señales;
- `NO_VALID_SETUP` como `VETO`;
- niveles accionables nulos para `VETO`;
- ausencia de `BUY_SETUP_ACTIVE`;
- preservación de filas y columnas de ranking.

## Criterios para migrar el ranking productivo

El cambio `change_production_ranking: true` solo debe aprobarse cuando:

1. CI y tests P0 pasan.
2. Varias corridas muestran resultados consistentes.
3. Ningún `NO_VALID_SETUP` aparece en el Top 20 operativo.
4. Ningún `VETO` asciende por calidad general del activo.
5. Ningún quote `LOW` aparece como `TRIGGER_CONFIRMED`.
6. Los setups válidos mejoran prioridad de forma interpretable.
7. No aumenta materialmente la concentración sectorial sin justificación.

La migración final debe realizarse en un commit separado para permitir rollback directo.
