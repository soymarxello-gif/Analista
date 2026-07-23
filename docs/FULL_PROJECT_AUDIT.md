# Auditoría integral del proyecto Analista

Fecha de referencia: 2026-07-18

## Alcance

Revisión de arquitectura, universo, datos, indicadores, setups, scoring, señales, ranking, reportes, pruebas, CI, persistencia de artefactos y riesgos operativos.

## Resumen ejecutivo

El proyecto ya tiene una base coherente para descubrir setups swing long-only y aplica una capa de normalización que evita señales operativas con filtros duros o cotizaciones defectuosas. Sin embargo, la lógica auditada todavía se ejecuta demasiado tarde: varias exclusiones se resuelven después de enriquecer datos, descargar precios y calcular scores. Además, el scanner elimina algunos fallos de liquidez antes de reportarlos, el modelo institucional es parcial, la calidad de datos no incorpora edad real de la cotización y la suite CI no cubre todavía todo el repositorio con lint estricto y tests de integración.

Estado global: **funcional, pero no listo para automatización ni para migrar el ranking productivo sin una fase adicional de endurecimiento**.

## Hallazgos críticos — P0

### P0-1. Los fallos de liquidez desaparecen del reporte

`scanner_engine` filtra `liquidity_pass == True` y descarta el resto antes de construir las filas finales. Esto impide conservar esos activos como `VETO` con trazabilidad completa.

Impacto:

- sesgo en métricas de cobertura y tasa de veto;
- imposibilidad de auditar por qué un símbolo fue eliminado;
- diferencia entre universo evaluado y universo reportado.

Corrección:

- no eliminar filas por liquidez;
- conservarlas con `signal=VETO` y `liquidity_fail` en `all_veto_reasons`;
- omitir únicamente scoring costoso posterior para filas ya vetadas.

### P0-2. Los filtros duros se aplican después de operaciones costosas

Precio, capitalización y tipo de instrumento se consolidan principalmente en el postprocesador. Para ese momento ya se ejecutaron enriquecimiento, descarga de precios, indicadores y parte del scoring.

Impacto:

- llamadas innecesarias a Yahoo Finance;
- mayor tiempo de ejecución y riesgo de rate limiting;
- candidatos inválidos recorren etapas que deberían estar cerradas.

Corrección:

- introducir una etapa `pre_scoring_gate` inmediatamente después del enriquecimiento mínimo;
- registrar el motivo del veto y evitar cálculos de opciones/fundamentales adicionales cuando ya existe un veto duro.

### P0-3. La calidad de quote no usa timestamp ni sesión

`quote_status` compara bid/ask con el último cierre, pero no dispone de timestamp de bid/ask ni distingue mercado abierto, premarket, postmarket o cierre anterior.

Impacto:

- falsos `STALE_POSSIBLE` fuera de sesión;
- quotes antiguos pueden parecer válidos si el precio está cerca;
- la señal puede depender de microestructura no comparable temporalmente.

Corrección:

- añadir `quote_timestamp`, `price_timestamp`, `market_session`, `quote_age_seconds`;
- degradar a `LOW` cuando la edad sea desconocida para una señal confirmada;
- usar último precio regular de la misma sesión como referencia.

### P0-4. Datos generados permanecen versionados

**Estado al 2026-07-21: RESUELTO.** Se retiraron del índice caches, logs, reportes, ZIP y notas de parches; `validate_repository_hygiene.py` impide su reintroducción en CI.

Aunque `.gitignore` excluye `cache/`, `logs/` y reportes generados, el repositorio contiene archivos históricos ya rastreados.

Impacto:

- crecimiento continuo del repositorio;
- exposición accidental de datos operativos;
- diffs ruidosos y menor reproducibilidad.

Corrección:

- retirar del índice caches, logs y scans históricos;
- conservar solo muestras pequeñas y anonimizadas en `tests/fixtures/`;
- publicar scans reales como artefactos de CI o releases, no como código fuente.

## Hallazgos altos — P1

### P1-1. El score institucional es incompleto

Actualmente se basa principalmente en opciones. No integra de forma sistemática insiders, acumulación/distribución, posicionamiento CFTC ni calidad/confianza por fuente.

Mejora:

- separar `options_score`, `insider_score`, `volume_profile_score` y `futures_positioning_score`;
- calcular `institutional_score` solo con componentes disponibles y registrar cobertura;
- impedir que la ausencia de datos equivalga a neutralidad positiva.

### P1-2. Opciones se consultan por orden de aparición

El límite `max_tickers_per_run` consume los primeros símbolos, no necesariamente los más relevantes.

Mejora:

- priorizar por setup preliminar, liquidez y cercanía al trigger;
- consultar opciones solo para candidatos `WATCHLIST` o superiores;
- registrar `options_skipped_reason`.

### P1-3. Sentimiento está fijado en 0.5

El scanner asigna `sentiment_score = 0.5`, lo que crea una contribución constante sin información real.

Mejora:

- eliminar temporalmente su peso o marcarlo como no disponible;
- habilitarlo únicamente cuando exista una fuente objetiva y auditable;
- aplicar ajuste contrarian explícito para extremos de put/call o crowding.

### P1-4. Fundamentales son secuenciales y con manejo de errores demasiado amplio

La descarga por ticker es secuencial y varios `except Exception` silencian el tipo de fallo.

Mejora:

- concurrencia limitada con backoff y jitter;
- errores tipados y métricas por fuente;
- cache con versión de esquema y timestamp dentro del payload;
- invalidación por campo, no solo por archivo completo.

### P1-5. No hay contrato de esquema formal para filas del scan

Las columnas se construyen como diccionarios dinámicos y el postprocesador completa campos tardíamente.

Mejora:

- definir modelos `CandidateInput`, `ScoredCandidate` y `AuditedCandidate`;
- validar tipos, valores permitidos y campos obligatorios;
- versionar el esquema de CSV/JSON.

### P1-6. Falta validación histórica de eficacia

Los tests comprueban invariantes lógicas, pero no miden si el ranking mejora resultados fuera de muestra.

Mejora:

- walk-forward por fecha de señal;
- métricas MFE/MAE, hit rate, expectancy, drawdown y tiempo al objetivo;
- comparación `final_score` vs `final_trade_score` sin look-ahead;
- segmentación por régimen, sector y setup.

## Hallazgos medios — P2

- El cálculo de retornos usa posiciones fijas de filas y no valida explícitamente huecos de calendario o calidad de historial.
- Los precios se descargan con `auto_adjust=False`; debe documentarse y normalizarse el tratamiento de splits/dividendos.
- Falta una política uniforme para NaN, infinito y valores fuera de rango en todos los scores.
- `score_breakdown` es texto; debería existir también como objeto JSON estructurado.
- Las razones se serializan como cadenas separadas por comas; deben conservarse como listas en JSON.
- El CLI mantiene `--no-intraday` sin comportamiento real.
- El nombre del CLI todavía dice “USA” aunque se permiten emisores extranjeros listados en EE. UU.
- El dashboard y los reportes deberían mostrar cobertura de fuentes y edad de datos.
- No hay presupuesto de llamadas, telemetría de latencia ni conteo de errores por proveedor.
- No existe una política explícita de reproducibilidad mediante `as_of` común para todo el scan.

## Revisión por subsistema

### Arquitectura

Fortalezas:

- separación razonable entre `data`, `indicators`, `setups`, `scoring`, `engine` y `reports`;
- postprocesador central con invariantes operativas;
- configuración externa y CI.

Debilidades:

- dos capas de decisión: scanner y postprocesador pueden divergir;
- diccionarios sin contrato formal;
- lógica crítica repartida entre clasificación y normalización.

Recomendación: convertir el postprocesador en la única máquina de estados y hacer que el scanner produzca hechos, no decisiones finales.

### Universo y liquidez

- mantener acciones comunes y ADR líquidos;
- distinguir `unknown_security_type` de exclusión confirmada;
- no tratar metadata ausente como equivalente a instrumento excluido sin una razón específica;
- preservar todos los vetos en el reporte de auditoría.

### Indicadores y setups

- validar warm-up mínimo por indicador;
- añadir flags de suficiencia de historia;
- unificar nomenclatura y escala de scores;
- exigir confirmación de volumen para breakouts;
- mantener divergencias y estructura como evidencia, no como disparadores aislados.

### Riesgo

- implementar completamente `stop_atr_multiple` y estados `too_tight`, `aggressive`, `preferred`, `too_wide`;
- calcular slippage estimado desde spread y liquidez;
- ajustar R/R por slippage y gap risk;
- mantener ejecución manual.

### Ranking

- continuar la auditoría paralela de ranking;
- no migrar a `final_trade_score` hasta completar walk-forward;
- añadir estabilidad de ranking entre corridas y sensibilidad a campos faltantes.

### Reportes

- JSON con listas y objetos nativos;
- CSV aplanado para auditoría;
- Markdown/HTML con resumen, calidad y advertencias;
- incluir `schema_version`, `scan_id`, `as_of`, `config_hash` y `code_commit`.

### Tests y CI

Cobertura mínima recomendada:

1. unit tests de todos los scores e indicadores;
2. contract tests de clientes Yahoo;
3. integration test con fixtures deterministas;
4. property tests de invariantes de señales;
5. regression test de esquema de reportes;
6. full Ruff, formato y type checking;
7. smoke scan sin red con fixtures.

## Plan de corrección

### Iteración A — integridad y trazabilidad

- preservar vetos de liquidez;
- adelantar filtros duros;
- introducir esquema versionado;
- retirar artefactos generados del índice;
- limpiar anomalías sintácticas y ampliar CI.

### Iteración B — calidad de datos

- timestamps y edad de quote;
- sesión de mercado;
- cache versionada;
- backoff, telemetría y fallback de fuentes;
- campos de cobertura y confianza.

### Iteración C — modelo de trading

- ATR agresivo completo;
- score institucional modular;
- sentimiento contrarian real;
- ranking auditado con estabilidad y sensibilidad.

### Iteración D — validación cuantitativa

- dataset histórico reproducible;
- walk-forward;
- comparación de rankings;
- criterios de promoción a producción.

## Criterios de salida

El proyecto podrá considerarse listo para una fase de producción manual estable cuando:

- todos los vetos sean trazables;
- ningún filtro duro se aplique después de scoring costoso;
- cada dato crítico tenga fuente, timestamp y estado;
- CI ejecute tests, lint completo y validación de esquema;
- los reportes sean reproducibles mediante commit/config/as-of;
- el ranking nuevo demuestre mejora fuera de muestra sin elevar vetos o setups inválidos;
- `BUY_SETUP_ACTIVE` y ejecución automática permanezcan deshabilitados.
