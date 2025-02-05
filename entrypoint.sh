#!/bin/bash

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

if [ "$DEBUG" = "True" ]
then
  echo "DEBUG on ####################################################################################"
  python manage.py makemigrations
  python manage.py migrate

  django-admin makemessages -l de
  django-admin makemessages -l en
  django-admin makemessages -l es

  #crontab /app/cron
else
  echo "DEBUG off ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"

  cd /app/datalab/static
  npm install
  cd /app

  python manage.py migrate --settings=datalab.settings.production
  python manage.py collectstatic --settings=datalab.settings.production --no-input --clear # also required by wagtail_localize
  python manage.py compress --settings=datalab.settings.production --force # SCSS
  python manage.py update_index --settings=datalab.settings.production
  python manage.py check --deploy

  # ./manage.py fixtree --settings=bioessentials.settings.prod
  # ./manage.py update_index --settings=bioessentials.settings.prod
  # ./manage.py search_garbage_collect --settings=bioessentials.settings.prod
  # ./manage.py wagtail_update_image_renditions --settings=bioessentials.settings.prod

  #crontab /app/cron # run this by starting cron in entrypoint.sh with "service cron start"
fi

# set timezone also in TIME_ZONE in settings for system wide settings (just to be shure)
rm -rf /etc/localtime
ln -s /usr/share/zoneinfo/Europe/Berlin /etc/localtime

crontab /app/cron
service cron enable
service cron start
printenv > /etc/environment # need to export all env to this file to access them from crontab

exec "$@"
