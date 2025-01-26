FROM python:3.12-slim-bookworm AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libsass-dev

RUN pip install --upgrade pip
RUN pip install wheel
RUN pip wheel --no-cache-dir --wheel-dir=/build/wheels libsass


FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV APP_HOME=/app
ENV PATH="/app/.local/bin:${PATH}"

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
    npm \
    cron \
 && apt-get dist-upgrade -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR $APP_HOME
COPY . .

RUN pip install --upgrade pip
RUN mkdir wheels
COPY --from=builder /build/wheels/ wheels/
RUN pip install wheels/*.whl
RUN pip install --no-cache-dir -v -r /app/Tooling/prod/requirements.txt

ENTRYPOINT ["/app/entrypoint.sh"]
