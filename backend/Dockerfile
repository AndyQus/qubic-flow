FROM python:3.12-slim AS compiler
ARG TARGETARCH

WORKDIR /app

RUN apt-get update && apt-get install -y gcc build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt cython setuptools

COPY . .

# Cython compilation only on amd64 — ARM64 via QEMU emulation is too slow (6h+ timeout)
RUN if [ "$TARGETARCH" = "amd64" ]; then \
      python compile.py build_ext --inplace && \
      rm app/services/tax_engine.py app/services/sync_engine.py app/services/export_service.py app/services/label_service.py; \
    fi


FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=compiler /app .

RUN mkdir -p /app/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
