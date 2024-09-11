#!/bin/bash

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

python manage.py makemigrations #--settings=bioessentials.settings.dev
        # ./manage.py syncdb --noinput --no-initial-data # only temporary
python manage.py migrate #--settings=bioessentials.settings.dev

#python manage.py loaddata dbbackups/dump_17-10-2022_13_43.json # only once for restore

# 22.01.2023
# python manage.py collectstatic # required by wagtail_localize, only in prod

exec "$@"
