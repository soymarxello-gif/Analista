# Analista Android V3 — aceptación física en POCO X7 Pro / HyperOS

## Alcance

Esta validación confirma funcionamiento operativo local. La aplicación sigue siendo **long-only**, de revisión manual, sin ejecución automática, sin construcción automática de cartera y con `BUY_SETUP_ACTIVE` deshabilitado.

## 1. Verificar el paquete recibido

El artefacto de GitHub Actions debe contener:

- `analista-stable.apk`
- `analista-stable.apk.sha256`
- `release-manifest.txt`
- este checklist

En PowerShell, dentro de la carpeta descargada:

```powershell
Get-FileHash .\analista-stable.apk -Algorithm SHA256
Get-Content .\analista-stable.apk.sha256
```

Los hashes deben coincidir exactamente. El manifiesto debe identificar la versión, el `versionCode`, el commit y el modo `manual_review`.

## 2. Instalar o actualizar

Instalar el APK mediante ADB o el gestor de archivos de HyperOS. Si ya existe una versión estable firmada con la misma clave de pruebas, debe actualizar conservando Room, credenciales cifradas y corridas anteriores.

Comando opcional mediante ADB:

```text
adb install -r analista-stable.apk
```

No desinstalar previamente salvo que se esté realizando una prueba específica de instalación limpia.

## 3. Permisos y energía en HyperOS

Los nombres exactos pueden variar según la versión de HyperOS. Confirmar:

- notificaciones permitidas;
- alarmas exactas permitidas;
- inicio automático habilitado;
- batería configurada como **Sin restricciones** para Analista;
- actividad en segundo plano permitida;
- fecha, hora y zona horaria automáticas;
- no aplicar limpieza automática de la aplicación.

Reiniciar el teléfono y comprobar que la próxima ejecución programada continúa visible en Diagnóstico.

## 4. Configurar Alpaca

Dentro de la aplicación:

1. Introducir `API key`, `secret` y feed autorizado.
2. Ejecutar la prueba de conexión.
3. Confirmar que las credenciales permanecen después de cerrar y abrir la aplicación.
4. Confirmar que no aparecen las credenciales en pantallas, logs ni exportaciones.

## 5. Ejecutar una corrida real

Con conexión estable:

1. Lanzar un scan manual.
2. Esperar a que finalice sin cerrar la aplicación.
3. Abrir Diagnóstico.
4. Confirmar que la corrida seleccionada muestra identidad de universo, configuración, motores, calendario y proveedores.

## 6. Gate institucional esperado

La aceptación sólo es válida cuando:

- no existen violaciones P0;
- todos los contratos provienen de una decisión final elegible;
- ningún `TRIGGER_CONFIRMED` utiliza cotización `STALE` o `UNKNOWN`;
- ningún conflicto institucional alto supera `WATCHLIST`;
- los stops de 0,60–1,00 ATR cumplen R/R, estructura, setup, trigger y calidad de quote;
- reproducibilidad figura `COMPLETE`;
- replay figura `COMPLETE` y sin mismatches;
- no faltan datasets requeridos;
- los hashes de configuración y universo son válidos;
- el ranking legacy permanece activo salvo promoción predictiva aprobada.

## 7. Revisar candidatos

Abrir al menos tres candidatos y comprobar:

- señal técnica preliminar y señal final diferenciadas;
- setup específico, nunca `BREAKOUT_OR_PULLBACK`;
- precio ejecutable, trigger y máximo de entrada;
- frescura y proveedor de la cotización;
- stop, tipo de stop, target y resistencia relevante;
- R/R, riesgo monetario, acciones y valor de posición;
- contexto macro, fundamental e institucional;
- ajuste contrarian, coberturas, vetos y penalizaciones.

`TRIGGER_CONFIRMED` significa candidato confirmado para **revisión manual**, no orden de compra.

## 8. Backtest y replay

En Backtest confirmar que existen, cuando correspondan:

- fill de entrada;
- gaps de entrada o stop;
- precio y motivo de salida;
- retorno en R;
- costes y slippage;
- MFE y MAE;
- estado ambiguo cuando stop y target aparecen en la misma barra diaria.

Ejecutar nuevamente el replay de la corrida seleccionada. Debe conservar el mismo estado y hashes.

## 9. Prueba de resiliencia

Realizar una segunda corrida con una de estas condiciones controladas:

- Alpaca temporalmente desconectado para comprobar fallback a Yahoo;
- conexión de red desactivada para comprobar uso permitido de cache;
- reapertura tras reiniciar el dispositivo.

La aplicación debe degradar cobertura y confianza de forma explícita. No debe inventar valores neutrales ni producir niveles accionables con datos no ejecutables.

## 10. Scheduler

Confirmar:

- próxima ejecución a las 09:20 `America/New_York`;
- fines de semana y festivos NYSE omitidos;
- cierre anticipado reconocido por la versión del calendario;
- programación preservada después de reiniciar el teléfono.

## Resultado de aceptación

Registrar:

```text
Dispositivo: POCO X7 Pro
HyperOS:
Versión Analista:
Version code:
Commit:
Fecha y hora ET:
Alpaca feed:
Scan status:
Reproducibilidad:
Replay:
Scheduler tras reinicio:
Resultado: APROBADO / BLOQUEADO
Observaciones:
```

Cualquier fallo de firma, migración, credenciales, scheduler, reproducibilidad, replay o invariantes institucionales bloquea la aceptación.
