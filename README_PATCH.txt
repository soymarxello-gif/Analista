Parche de estabilización posterior a auditoría.

Archivos a reemplazar/agregar:
1) .gitignore
2) config.yaml
3) requirements.txt
4) README.md
5) engine/scanner_engine.py
6) tools/validate_project.py

Correcciones:
- Unifica data_sources.cache_ttl_minutes para fundamentals y options.
- Agrega .gitignore para evitar subir .venv, cache, logs y reports.
- Revalida universo después de enrich_metadata().
- Actualiza README con opciones, dashboard, arquitectura y limitaciones.
- Agrega versiones mínimas en requirements.txt.
- Agrega tools/validate_project.py para validar config.yaml sin claves duplicadas y compilar Python.

Uso:
cd "C:\Users\El otro Yo\Projects\ChatGPT\Analista"
.\.venv\Scripts\activate
python -m compileall .
python tools\validate_project.py
python run_scanner.py --max-candidates 30 --verbose --csv-out reports/latest_scan_audit_fix.csv --json-out reports/latest_scan_audit_fix.json

Git:
git status
git add .
git commit -m "Audit fixes: config, gitignore, validation and docs"
git push
