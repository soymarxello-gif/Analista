# Analista

Scanner MVP para detectar setups long-only de swing trading en acciones comunes estadounidenses.

## Reglas

- Solo acciones comunes USA.
- Solo largos.
- Horizonte operativo: 4 a 21 días.
- ETFs excluidos como activos operables.
- Yahoo/yfinance como fuente principal.
- Screener Yahoo/yfinance como primera reducción de universo.
- Motor propio de indicadores, setups, scoring y clasificación.

## Instalación

```powershell
cd "C:\Users\El otro Yo\Projects\ChatGPT\Analista"
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecución

```powershell
python run_scanner.py --verbose
```

Con límite:

```powershell
python run_scanner.py --max-candidates 300 --verbose
```

## Dashboard

```powershell
streamlit run ui/dashboard.py
```

## Señales

- `BUY_SETUP_ACTIVE`: setup confirmado, score alto y R:R suficiente.
- `READY_WAIT_TRIGGER`: buen candidato, espera confirmación.
- `WATCHLIST`: interesante, pero incompleto.
- `AVOID`: score o setup débil.
- `VETO`: falla crítica de liquidez, tendencia, R:R o setup.

## Advertencia

Este software es una herramienta analítica. No ejecuta órdenes, no constituye asesoría financiera y requiere validación manual.
