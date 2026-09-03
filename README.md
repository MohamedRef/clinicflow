# ClinicFlow

ClinicFlow coordinates non-clinical room, staff, consumable-inventory, and
appointment operations. It prevents room and staff overlaps, checks capability
and qualification coverage, reserves supplies at scheduling time, and protects
scheduled work from unsafe deactivation or maintenance windows.

Appointments use optimistic versions for terminal changes. Cancellation
releases reservations, while completion consumes the reserved stock. The JSON
repository writes a deterministic snapshot through an atomic replacement and
fails closed when persisted state is malformed or uses an unknown schema.

## Verification

```bash
python -m pip install --no-deps -r requirements-dev.lock
python -m pip check
python -m pip install --no-build-isolation --no-deps -e .
ruff format --check .
ruff check .
mypy src
pytest --cov --cov-report=term-missing
python -m pip wheel --no-build-isolation --no-deps --wheel-dir dist .
docker build --tag clinicflow-dependencies .
```

The committed lock includes transitive verification dependencies and the build
backend. Keep its direct pins aligned with `pyproject.toml`; test any regenerated
resolution in a fresh Python 3.12 environment before committing it. The Docker
image installs only the locked dependencies and contains no application source.

## Ownership

This private project is developed and owned by MohamedRef. Repository ownership,
project direction, review, and final decisions remain with MohamedRef.
