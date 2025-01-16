import environ
from .base import *

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)

#environ.Env.read_env(file_path)

# SECURITY WARNING: don't run with debug turned on in production!
# False if not in os.environ because of casting above
DEBUG = env('DEBUG')
# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS").split(" ")
SECRET_KEY = env("DJANGO_SECRET_KEY")
#file_path = Path(BASE_DIR + '/.env/.env.prod')
print('+++++++++++++++++ DEBUG = ' + str(DEBUG) + ' +++++++++++++++++++++++')

# EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD")

DATABASES = {
    "default": {
        "ENGINE": env("SQL_ENGINE"),
        "NAME": env('POSTGRES_DB'),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
    }
}

# INFLUX_BUCKET=env("INFLUX_BUCKET")
# INFLUX_ORG=env("INFLUX_ORG")
# INFLUX_URL=env("INFLUX_URL")
# INFLUX_TOKEN = env("INFLUX_TOKEN")
#
# MAPBOX_TOKEN = env("MAPBOX_TOKEN")
#
# MAPTILER_KEY=env("MAPTILER_KEY")

# WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
#     "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
#     "OPTIONS": {
#         "AUTH_KEY": "*************************",
#     },
# }
#
# HCAPTCHA_SITEKEY = env('HCAPTCHA_SITEKEY')
# HCAPTCHA_SECRET = env('HCAPTCHA_SECRET')

COMPRESS_OFFLINE = False  # Do not compress offline (takes some time at the start of deployment)
LIBSASS_OUTPUT_STYLE = 'compressed'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

SECURE_HSTS_SECONDS = 60
# SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# SECURE_SSL_REDIRECT = True
# X_FRAME_OPTIONS = 'DENY'

# import all system variables to Django, if not already defined
for key, value in env.ENVIRON.items():
    if key.isupper() and key not in globals():
        globals()[key] = value

try:
    from .local import *
except ImportError:
    pass

"""
Execute commands in this image
docker-compose exec web python manage.py createsuperuser --settings=app.settings.prod
"""
