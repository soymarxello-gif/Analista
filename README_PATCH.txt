Parche: dashboard con pestaña de opciones put/call.

Archivos a reemplazar/agregar:
1) ui/dashboard.py
2) .streamlit/config.toml

Qué incluye:
- Nueva pestaña "Opciones".
- Gráfico de distribución options_bias.
- Gráfico options_score vs put_call_volume_ratio.
- Ranking de flujo de opciones.
- Filtros por options_bias y options_score mínimo.
- Columnas de opciones en Oportunidades, Tabla completa y Diagnóstico.

Instrucciones:
cd "C:\Users\El otro Yo\Projects\ChatGPT\Analista"
.\.venv\Scripts\activate
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
streamlit run ui/dashboard.py

Luego selecciona en el panel lateral:
reports/latest_scan_options.csv
