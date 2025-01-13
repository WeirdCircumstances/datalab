#!/bin/bash

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

python manage.py migrate --settings=datalab.settings.production
python manage.py collectstatic --settings=datalab.settings.production --no-input --clear # also required by wagtail_localize
python manage.py compress --settings=datalab.settings.production --force # SCSS
python manage.py update_index --settings=datalab.settings.production
python manage.py check --deploy

# ./manage.py fixtree --settings=bioessentials.settings.prod
# ./manage.py update_index --settings=bioessentials.settings.prod
# ./manage.py search_garbage_collect --settings=bioessentials.settings.prod
# ./manage.py wagtail_update_image_renditions --settings=bioessentials.settings.prod

service cron enable
service cron start

exec "$@"