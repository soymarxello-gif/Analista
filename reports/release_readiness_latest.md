# Analista - release readiness check

- generated_at: 2026-06-10T22:07:53
- status: WARN
- release_ready: True
- release_mode: READY_WITH_WARNINGS

## Decision gate

- Estado WARN: release posible con advertencias documentadas.

## Componentes

- daily_validation: status=PASS, path=reports/daily_validation_summary.txt, error=
- daily_quality_gate: status=WARN, manual_review_allowed=True, manual_review_mode=REINFORCED, path=reports/daily_quality_gate_latest.json, error=
- encoding_audit: status=PASS, path=reports/encoding_audit_latest.json, error=

## Comandos de validación

### project_consistency_audit

- passed: True
- returncode: 0
- timed_out: False
- timeout_seconds: 120

stdout:
```text
=== ANALISTA PROJECT CONSISTENCY AUDIT ===

[legacy_terms]
- OK

[config]
- OK

[latest_scan]
- OK

Resultado: PASS
```

### pytest

- passed: True
- returncode: 0
- timed_out: False
- timeout_seconds: 300

stdout:
```text
........................................................................ [ 31%]
........................................................................ [ 62%]
........................................................................ [ 93%]
..............                                                           [100%]
============================== warnings summary ===============================
tests/test_calibration_engine_phase2_0.py::test_calibrate_weights_from_posttest
tests/test_calibration_engine_phase2_0.py::test_calibrate_weights_from_posttest
  C:\Users\El otro Yo\Projects\ChatGPT\Analista\.venv\Lib\site-packages\numpy\lib\_function_base_impl.py:3023: RuntimeWarning: invalid value encountered in divide
    c /= stddev[:, None]

tests/test_calibration_engine_phase2_0.py::test_calibrate_weights_from_posttest
tests/test_calibration_engine_phase2_0.py::test_calibrate_weights_from_posttest
  C:\Users\El otro Yo\Projects\ChatGPT\Analista\.venv\Lib\site-packages\numpy\lib\_function_base_impl.py:3024: RuntimeWarning: invalid value encountered in divide
    c /= stddev[None, :]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

## Operator index checks

- contains_daily_quality_gate_section: True
- contains_quality_gate_file: True
- contains_manual_review_allowed: True
- contains_manual_review_mode: True

## Issues

| severity | source | message |
| --- | --- | --- |
| WARN | daily_quality_gate_latest.json | daily_quality_gate está en WARN; release posible con validación reforzada. |

## Archivos críticos

| path | exists | size_bytes | modified |
| --- | --- | --- | --- |
| tools/daily_validation.py | True | 25029 | 2026-06-10T20:49:13 |
| tools/daily_operator_index.py | True | 29597 | 2026-06-10T21:16:35 |
| tools/daily_quality_gate.py | True | 22265 | 2026-06-10T20:52:41 |
| tools/daily_run_manifest.py | True | 17919 | 2026-06-10T17:41:52 |
| tools/encoding_audit.py | True | 9589 | 2026-06-10T19:17:01 |
| tools/project_preflight.py | True | 11631 | 2026-06-10T14:40:51 |
| tools/reports_cleanup.py | True | 9150 | 2026-06-10T13:35:47 |
| reports/daily_validation_summary.txt | True | 33255 | 2026-06-10T21:56:57 |
| reports/daily_quality_gate_latest.json | True | 4325 | 2026-06-10T21:56:55 |
| reports/daily_quality_gate_latest.md | True | 2173 | 2026-06-10T21:56:55 |
| reports/daily_operator_index.md | True | 5996 | 2026-06-10T21:56:51 |
| reports/daily_run_manifest_latest.json | True | 17616 | 2026-06-10T21:56:52 |
| reports/daily_run_manifest_latest.md | True | 13567 | 2026-06-10T21:56:52 |
| reports/encoding_audit_latest.json | True | 123211 | 2026-06-10T21:56:55 |
| reports/encoding_audit_latest.md | True | 334 | 2026-06-10T21:56:55 |
| reports/project_preflight_latest.json | True | 5359 | 2026-06-10T21:56:25 |
| reports/project_preflight_latest.md | True | 2705 | 2026-06-10T21:56:25 |
| reports/latest_scan_audited.csv | True | 783379 | 2026-06-10T21:56:47 |
| reports/manual_review_latest.csv | True | 32794 | 2026-06-10T21:56:57 |
| reports/manual_review_top.csv | True | 18754 | 2026-06-10T21:56:57 |