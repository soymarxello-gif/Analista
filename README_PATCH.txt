Parche Phase 2.3: Operational Priority Score.

Objetivo:
Crear una prioridad operativa separada del final_score.

final_score responde:
- qué tan atractiva es la tesis/setup

operational_priority_score responde:
- qué tan prioritario es revisar este candidato hoy considerando:
  data quality, liquidez, fuente del screener, confianza en opciones, bid/ask y vetos

Archivos:
- scoring/operational_priority.py
- tests/test_operational_priority_phase2_3.py
- CONFIG_FRAGMENT_PHASE2_3.yaml
- SCANNER_ENGINE_PHASE2_3_NOTES.md
- DASHBOARD_PHASE2_3_NOTES.md

Validación:
cd "C:\Users\El otro Yo\Projects\ChatGPT\Analista"
.\.venv\Scripts\activate

python -m compileall .
pytest tests\test_operational_priority_phase2_3.py

Uso después de integrar en scanner_engine:
python run_scanner_audited.py --max-candidates 300 --verbose --csv-out reports/latest_scan_phase2_3.csv --json-out reports/latest_scan_phase2_3.json

Verificación:
python -c "import pandas as pd; df=pd.read_csv('reports/latest_scan_phase2_3.csv'); cols=['ticker','pre_veto_signal','signal','final_score','operational_priority_score','operational_priority_bucket','source_quality_score','data_quality_confidence','options_bias','operational_priority_warning']; print(df[cols].head(20).to_string(index=False))"
