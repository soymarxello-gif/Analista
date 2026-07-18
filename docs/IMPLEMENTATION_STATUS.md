# Estado de implementación de la auditoría

## Iteración 1 — contrato y control de salida

Estado: **implementada y en validación CI**.

Cambios incluidos:

- contrato formal `contracts/scan_schema.py`;
- versión de esquema `2.0` añadida a cada scan;
- validación bloqueante antes de guardar CSV/JSON;
- pruebas para columnas obligatorias, señales, quotes y niveles accionables;
- gate específico en GitHub Actions;
- espejo local sincronizado en `/mnt/data/Analista`.

Validación local:

```text
pytest tests/test_scan_schema.py -q
5 passed
```

## Próximos bloques

1. Preservar fallos de liquidez como filas `VETO` auditables.
2. Aplicar filtros duros antes de descargas y scoring costosos.
3. Añadir timestamp, edad y sesión a la calidad de quote.
4. Versionar cache y retirar artefactos generados del control de versiones.
5. Priorizar consultas de opciones por calidad preliminar del setup.
6. Incorporar telemetría, backoff y pruebas sin red.
7. Añadir validación walk-forward y métricas MFE/MAE.
