# Open-Loop Benchmarks

Tigrcorn keeps external open-loop benchmarks separate from strict release
promotion performance evidence. The strict matrix remains
`docs/review/performance/performance_matrix.json`; wrk2 and Vegeta use their
own opt-in matrices and artifact roots.

## wrk2

wrk2 is used for constant offered-load HTTP/1.1 pressure profiles:

```bash
python tools/run_perf_matrix.py --matrix docs/review/performance/wrk2_benchmark_matrix.json --profile wrk2_http11_baseline_constant_rate
```

Artifacts are written under
`docs/review/performance/artifacts/wrk2_open_loop_current` unless
`--artifact-root` is supplied. The default binary name is `wrk`; override it per
profile with `driver_config.binary` when the local executable is named
`wrk2`.

## Vegeta

Vegeta is used for scripted offered-load patterns:

```bash
python tools/run_perf_matrix.py --matrix docs/review/performance/vegeta_benchmark_matrix.json --profile vegeta_http11_recovery_after_overload
```

Artifacts are written under
`docs/review/performance/artifacts/vegeta_open_loop_current` unless
`--artifact-root` is supplied. The Vegeta profiles preserve per-phase metadata
inside `metrics.profile_metadata.phases`.

## Boundary

These matrices are local/operator benchmark lanes. They do not feed release
promotion gates, release evidence rows, or the phase6/phase9g strict artifact
roots unless a later governed change explicitly promotes selected benchmark
results.
