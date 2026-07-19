# Analista Android

Aplicación Android autónoma para swing trading long-only. No requiere PC ni servidor propio después de instalarse.

## Funciones incluidas

- Descarga directa de históricos diarios desde Yahoo Finance.
- Indicadores locales: SMA20/50, RSI14, MACD, estocástico, ATR14 y volumen relativo.
- Señales long-only con control de sobreextensión y confirmación de volumen.
- Persistencia Room de todas las corridas, incluidas las fallidas.
- Historial local apto para backtesting posterior.
- Calendario NYSE en `America/New_York`, feriados y horario de verano.
- Programación diaria a las 09:20 ET con alarma exacta o ventana degradada.
- Foreground service y notificación del resultado.
- Interfaz Jetpack Compose.

## Compilar

Abrir `android/` con Android Studio o ejecutar con Gradle 8.11.1:

```bash
gradle :app:testDebugUnitTest :app:assembleDebug
```

El APK queda en `app/build/outputs/apk/debug/app-debug.apk`.

## Versión 1.1

- Navegación por Resumen, Historial, Backtest y Diagnóstico.
- Razones técnicas traducidas.
- Contexto macro local: US10Y, US30Y, VIX, DXY, WTI y Bitcoin.
- Reintentos, fallback entre hosts Yahoo y cache local de 72 horas.
- Telemetría visible por corrida.
- Seguimiento preliminar de retornos de señales históricas.
- Diagnóstico de notificaciones, alarmas exactas y ejecuciones automáticas.
