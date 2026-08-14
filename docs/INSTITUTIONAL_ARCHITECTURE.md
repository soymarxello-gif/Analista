# Arquitectura institucional de Analista

## Invariantes

1. Cada dato tiene `event_time`, `available_at`, fuente, feed y estado.
2. Una simulación solo puede leer revisiones con `available_at <= decision_time`.
3. El universo se reconstruye para la fecha; no se usa la lista actual para el pasado.
4. No hay `top market cap`, `top ADV` ni cupo sectorial antes de evaluar el setup.
5. ETF no exige market cap corporativa; en acciones, un market cap conocido bajo USD 1.500 millones excluye, pero el dato ausente solo genera advertencia.
6. IEX no confirma ADV, RVOL ni trigger. OPRA es obligatorio para ejecución de opciones.
7. Una señal no desaparece si el ticker deja el universo.
8. Mercado cerrado conserva el setup como `READY_FOR_NEXT_SESSION`.
9. Macro, fundamentales, earnings y opciones son contexto posterior: nunca filtran, penalizan, reordenan ni bloquean un setup técnico.
10. La ausencia de contexto se presenta como `NO_DATA`, por ejemplo `Sin datos de opciones`.

## Componentes

- `institutional.store`: security master, barras, señales, outcomes, source health y runs.
- `institutional.universe`: elegibilidad completa point-in-time y funnel.
- `institutional.features`: discovery técnico y agregado semanal calendario.
- `institutional.providers` / `source_adapters`: contratos ejecutables y parsers oficiales.
- `institutional.ingestion`: descarga incremental Nasdaq Trader/Alpaca, metadata de capitalización trazable e importación de bundles.
- `institutional.runtime`: único orquestador productivo desde store hasta señal y shadow run.
- `institutional.context_advisory`: adjunta cobertura y advertencias después del discovery sin alterar la señal técnica.
- `institutional.decision`: ciclo de vida sin mezclar alfa con confianza de datos.
- `institutional.outcomes`: evaluación por evento y horizontes fijos.
- `institutional.walkforward`: folds rodantes/expansivos, embargo y bootstrap.
- `institutional.shadow`: muestra bloqueada y configuración inmutable.
- `institutional.api`: ingestión, ejecución y lectura autenticada para Android.

## Seguridad

- El backend conserva las claves de proveedores; no deben exponerse en respuestas de API.
- Para cualquier bind distinto de localhost, `ANALISTA_API_TOKEN` es obligatorio y Android debe enviar `Authorization: Bearer`.
- Android usa Keystore para su autenticación y tiene backup/extracción desactivados.
- CI publica solo APK debug. Producción requiere keystore privado o Play App Signing.
