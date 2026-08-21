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
python -m pip install -e '.[dev]'
ruff format --check .
ruff check .
mypy src
pytest --cov --cov-report=term-missing
docker build --tag clinicflow-dependencies .
```

## Ownership

This private project is developed and owned by MohamedRef. Repository ownership,
project direction, review, and final decisions remain with MohamedRef.
