# Two stages so the runtime image carries no build toolchain and no dev
# dependencies. Wheels are built once and copied in.

FROM python:3.11-slim AS builder

WORKDIR /build

# Only the manifest, so a code change does not invalidate the dependency layer.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim AS runtime

# PYTHONDONTWRITEBYTECODE: the filesystem is ephemeral, .pyc files are waste.
# PYTHONUNBUFFERED: without it, logs sit in a buffer and a crash loses them,
# which is the exact moment logs matter.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY src ./src

# Non-root. A container that never needs to write to its own filesystem should
# not be able to.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Render, Cloud Run and Fly all inject PORT and expect the process to bind it.
# Shell form so the variable is expanded at start, with a local default.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
