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

# RUN groupadd -r appuser && useradd -r -g appuser -d $APP_HOME -s /sbin/nologin -c "Docker image user" appuser

# RUN mkdir -p $APP_HOME && chown -R appuser:appuser $APP_HOME

ENV APP_HOME=/app

WORKDIR /wheels

COPY Tooling/prod/requirements.txt requirements_prod.txt
COPY Tooling/dev/requirements.txt requirements_dev.txt
RUN pip install --upgrade pip
COPY --from=builder /build/wheels/ .
RUN pip install *.whl
RUN pip install --no-cache-dir -v -r requirements_dev.txt

#WORKDIR /app

#RUN pwd
#RUN ls -lah /app
#RUN ls -lah /app/Tooling/dev/

#COPY Tooling/dev/entrypoint.sh entrypoint.sh
#RUN sed -i 's/\r$//g' entrypoint.sh
#RUN chmod +x entrypoint.sh

##RUN chmod +x /app/Tooling/prod/borg.sh
##RUN mkdir -p /root/.ssh/
##RUN echo "|1|lHy6GJWK+u1oI/tBXbUVhXTQxMs=|PIkT7J9hOse4/3GeFjGMAATP9t0= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMS3185JdDy7ffnr0nLWqVy8FaAQeVh1QYUSiNpW5ESq" > /root/.ssh/known_hosts

## run this by starting cron in entrypoint.sh with "service cron start"
#RUN crontab /app/Tooling/dev/cron

## set timezone also in TIME_ZONE in settings for system wide settings (just to be shure)
#RUN rm -rf /etc/localtime
#RUN ln -s /usr/share/zoneinfo/Europe/Berlin /etc/localtime

#RUN cat /app/Tooling/dev/entrypoint.sh

# this file does exist after this file is complete!
ENTRYPOINT ["/app/entrypoint.sh"]