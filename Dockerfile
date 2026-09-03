FROM python:3.12-slim

WORKDIR /workspace
COPY requirements-dev.lock .
RUN pip install --no-cache-dir --no-deps -r requirements-dev.lock && pip check
