# Scheduler model

TigrCorn isolates scheduling policy from protocol code.

The scheduler owns:

- max concurrent connections
- max concurrent tasks
- max streams per session
- fairness / dispatch policy
- cancellation and graceful shutdown

The current archive now ships a package-owned production scheduler in `src/tigrcorn/scheduler/runtime.py`.
That runtime component owns connection admission, task quota enforcement, task draining, and graceful shutdown for server-internal scheduled work.
The lighter-weight policy objects under `src/tigrcorn/scheduler/` remain available for direct unit testing and smaller integration points.
