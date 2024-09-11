#!/bin/bash

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# export PATH="/app/venv/bin:$PATH"

# Debug: Ausgabe des PATH und Verfügbarkeit von gunicorn
# python -m site
# echo "PATH: $PATH"
# whoami
# ls -lah /app/
# ls -lah /app/venv/
# ls -lah /app/venv/bin
# which gunicorn
# gunicorn --version
# /app/venv/bin/gunicorn --workers=1 sensebox.wsgi:application --bind 0.0.0.0:8000 --timeout 600

# python manage.py makemigrations allauth --settings=bioessentials.settings.prod
# python manage.py makemigrations home --settings=bioessentials.settings.prod
# python manage.py makemigrations blog --settings=bioessentials.settings.prod
# python manage.py makemigrations analysis --settings=bioessentials.settings.prod
# python manage.py makemigrations --settings=bioessentials.settings.prod

# Restore
# python manage.py syncdb --noinput --no-initial-data # only temporary is this deprecated?!?!?

python manage.py migrate --settings=sensebox.settings.production
python manage.py collectstatic --settings=sensebox.settings.production --no-input --clear # also required by wagtail_localize
python manage.py compress --settings=sensebox.settings.production --force # SCSS
python manage.py update_index --settings=sensebox.settings.production
python manage.py check --deploy

# ./manage.py fixtree --settings=bioessentials.settings.prod
# ./manage.py update_index --settings=bioessentials.settings.prod
# ./manage.py search_garbage_collect --settings=bioessentials.settings.prod
# ./manage.py wagtail_update_image_renditions --settings=bioessentials.settings.prod

service cron enable
service cron start

exec "$@"
