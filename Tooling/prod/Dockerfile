FROM python:3.12-slim-bookworm AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libsass-dev

RUN pip install --upgrade pip
RUN pip install wheel
RUN pip wheel --no-cache-dir --wheel-dir=/build/wheels libsass autobahn wagtail-django-recaptcha rcssmin rjsmin


FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
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
    borgbackup \
    openssh-client \
    cron \
 && apt-get dist-upgrade -y \
 && rm -rf /var/lib/apt/lists/*

# RUN groupadd -r appuser && useradd -r -g appuser -d $APP_HOME -s /sbin/nologin -c "Docker image user" appuser

# RUN mkdir -p $APP_HOME && chown -R appuser:appuser $APP_HOME

WORKDIR $APP_HOME
COPY . .
# COPY --chown=appuser:appuser . .
# RUN chown -R appuser:appuser $APP_HOME
# USER appuser

# ENV VIRTUAL_ENV=venv
# RUN python3 -m venv /app/$VIRTUAL_ENV
# RUN python3 -m venv venv
#ENV PATH="$APP_HOME/$VIRTUAL_ENV/bin:$PATH"
# ENV PATH="/app/venv/bin:$PATH"

##########################
#
# create app user: https://www.phooky.com/blog/deploy-your-wagtail-webpage-with-docker-postgresql-gunicorn-nginx/
#
##########################

RUN pip install --upgrade pip
RUN mkdir wheels
COPY --from=builder /build/wheels/ wheels/
RUN pip install wheels/*.whl
RUN pip install --no-cache-dir -v -r /app/Tooling/prod/requirements.txt

RUN sed -i 's/\r$//g' /app/Tooling/prod/entrypoint.sh
RUN chmod +x /app/Tooling/prod/entrypoint.sh

RUN chmod +x /app/Tooling/prod/borg.sh
RUN mkdir -p /root/.ssh/
RUN echo "|1|lHy6GJWK+u1oI/tBXbUVhXTQxMs=|PIkT7J9hOse4/3GeFjGMAATP9t0= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMS3185JdDy7ffnr0nLWqVy8FaAQeVh1QYUSiNpW5ESq" > /root/.ssh/known_hosts

RUN crontab /app/Tooling/prod/cron_borg # run this by starting cron in entrypoint.sh with "service cron start"

ENTRYPOINT ["/app/Tooling/prod/entrypoint.sh"]
