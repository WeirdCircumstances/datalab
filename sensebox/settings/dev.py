import environ

from .base import *

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-(urllh-5kozu8jc$f2633$i2dtv@n3tfn1c=1590(-_$9w(-t5"

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": env("SQL_ENGINE"),
        "NAME": env('POSTGRES_DB'),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),  # "localhost", #
        "PORT": env("POSTGRES_PORT"),
    }
}

try:
    from .local import *
except ImportError:
    pass
