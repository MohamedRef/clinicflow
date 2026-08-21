FROM python:3.12-slim

WORKDIR /workspace
RUN pip install --no-cache-dir mypy==1.19.1 pytest==9.0.2 pytest-cov==7.0.0 ruff==0.15.5 setuptools==80.9.0 wheel==0.46.2
