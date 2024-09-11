FROM python:3.12-slim-bookworm AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libsass-dev

RUN pip install --upgrade pip
RUN pip install wheel
RUN pip wheel --no-cache-dir --wheel-dir=/build/wheels libsass autobahn wagtail-django-recaptcha rcssmin rjsmin


FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install system packages required by Wagtail and Django.
RUN apt update
RUN apt install -y --no-install-recommends libjpeg62-turbo-dev zlib1g-dev libwebp-dev libsm6 libxrender1 libxext6 libgl1-mesa-glx libglib2.0-0 gettext npm
# RUN apt dist-upgrade -y
    # && \
RUN rm -rf /var/lib/apt/lists/*

# https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
# geht noch besser
#RUN python3 -m venv venv

# ENV VIRTUAL_ENV=/opt/venv
# RUN python3 -m venv $VIRTUAL_ENV
# ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /wheels

COPY Tooling/prod/requirements.txt requirements_prod.txt
COPY Tooling/dev/requirements.txt requirements_dev.txt
RUN pip install --upgrade pip
#COPY --from=builder /usr/local/lib/python3.12/site-packages/libsass* /usr/local/lib/python3.12/site-packages/
COPY --from=builder /build/wheels/ .
RUN pip install *.whl
RUN pip install --no-cache-dir -v -r requirements_dev.txt
#RUN xargs poetry add < requirements.txt

#WORKDIR /opt/project/bioessentials/static/
#WORKDIR /app
# Run this in the container ...
#RUN npm add mjml htmx.org dropzone@5
# run those steps by hand once in a while

WORKDIR /app

COPY . .

RUN sed -i 's/\r$//g' /app/Tooling/dev/entrypoint.sh
RUN chmod +x /app/Tooling/dev/entrypoint.sh

ENTRYPOINT ["/app/Tooling/dev/entrypoint.sh"]