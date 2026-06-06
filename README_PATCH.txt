Parche: calidad, tests y CI.

Archivos a agregar/reemplazar:
1) requirements-dev.txt
2) pyproject.toml
3) .github/workflows/ci.yml
4) tests/test_config.py
5) tests/test_final_score.py
6) tests/test_signal_classifier.py
7) tests/test_options_score.py
8) tools/quick_check.py

Qué agrega:
- Tests de config.yaml sin duplicados.
- Test de suma de scoring_weights = 100.
- Test de pesos internos de options_flow = 1.
- Tests de final_score.
- Tests de signal_classifier.
- Tests de options_score.
- GitHub Actions CI en cada push/PR a main.
- Script local tools/quick_check.py.

Uso local:
cd "C:\Users\El otro Yo\Projects\ChatGPT\Analista"
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
python tools\quick_check.py

Git:
git add .
git commit -m "Add tests and CI quality checks"
git push
