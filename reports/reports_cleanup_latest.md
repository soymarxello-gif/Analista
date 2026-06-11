# Analista - reports cleanup

- generated_at: 2026-06-11T01:05:00
- status: PASS
- mode: DRY_RUN
- reports_dir: reports
- archive_dir: reports/tmp/temp_reports_20260611_010500
- candidate_count: 0
- moved_count: 0

## Resultado

_No se detectaron reportes temporales._

## Regla de seguridad

- Este script no borra archivos.
- Sin `--apply`, solo simula la limpieza.
- Con `--apply`, mueve temporales a `reports/tmp/`.
- Los reportes operativos `latest`, `manual_review`, `daily_operator_index`, analytics y bitácora real están protegidos.