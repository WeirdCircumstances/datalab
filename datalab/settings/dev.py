import environ

from .base import *

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False),
)

DEBUG = env('DEBUG')
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS").split(" ")

print('+++++++++++++++++ DEBUG = ' + str(DEBUG) + ' +++++++++++++++++++++++')

#DJANGO_SETTINGS_MODULE=env('DJANGO_SETTINGS_MODULE')

# SECURITY WARNING: keep the secret key used in production secret!
#SECRET_KEY = env("DJANGO_SECRET_KEY")

# SECURITY WARNING: define the correct hosts in production!
#ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS").split(" ")

#INFLUX_BUCKET=env("INFLUX_BUCKET")
#INFLUX_ORG=env("INFLUX_ORG")
#INFLUX_URL=env("INFLUX_URL")
#INFLUX_TOKEN = env("INFLUX_TOKEN")

#MAPBOX_TOKEN = env("MAPBOX_TOKEN")
#MAPTILER_KEY=env("MAPTILER_KEY")

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": env("SQL_ENGINE"),
        "NAME": env('DB_NAME'),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)

# import all system variables to Django, if not already defined
for key, value in env.ENVIRON.items():
    if key.isupper() and key not in globals():
        globals()[key] = value

try:
    from .local import *
except ImportError:
    pass
