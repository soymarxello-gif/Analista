# Analista Android

Aplicación Android autónoma para swing trading long-only. No requiere PC ni servidor propio después de instalarse.

## Funciones

- Descarga directa de históricos diarios desde Yahoo Finance.
- Indicadores locales: SMA20/50, RSI14, MACD, estocástico, ATR14 y volumen relativo.
- Señales long-only con control de sobreextensión y confirmación de volumen.
- Persistencia Room de todas las corridas.
- Calendario NYSE en America/New_York y programación a las 09:20 ET.
- Foreground service, notificaciones e interfaz Jetpack Compose.

## Compilar

Abrir `android/` con Android Studio o ejecutar con Gradle 8.11.1:

```bash
gradle :app:testDebugUnitTest :app:assembleDebug
```

El APK queda en `app/build/outputs/apk/debug/app-debug.apk`.
