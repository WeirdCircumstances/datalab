FROM python:3.12-slim-bookworm AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libsass-dev

RUN pip install --upgrade pip
RUN pip install wheel
RUN pip wheel --no-cache-dir --wheel-dir=/build/wheels libsass


FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV APP_HOME=/app
ENV PATH="/app:/app/.local/bin:${PATH}"

RUN apt-get update \
&& apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    gettext \
    borgbackup \
    openssh-client \
    cron \
    nano \
 && apt-get dist-upgrade -y \
 && rm -rf /var/lib/apt/lists/*

ENV APP_HOME=/app

WORKDIR /wheels

COPY Tooling/prod/requirements.txt requirements_prod.txt
COPY Tooling/dev/requirements.txt requirements_dev.txt

RUN pip install --upgrade pip
COPY --from=builder /build/wheels/ .
RUN pip install *.whl
RUN pip install --no-cache-dir -v -r requirements_dev.txt

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]