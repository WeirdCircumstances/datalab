#!/bin/bash

#/bin/bash # here without ! I made it work, but this line is maybe not important here

FILE_PATH=/app/

cd ${FILE_PATH}

set -a
source /app/.env/.env.prod
set +a

## this is the minimal working example of a working backup. Nothing extra, working 16/10/22
/usr/local/bin/python /app/manage.py dumpdata                           \
        --settings=sensebox.settings.production                  \
        --natural-foreign --indent 2                                    \
        -e auth.permission                                              \
        -e contenttypes                                                 \
        -e wagtailcore.groupcollectionpermission                        \
        -e wagtailcore.grouppagepermission                              \
        -e sessions                                                     \
        -e wagtailimages.rendition                                      \
        -o ./dump.json

# Finding the correct way to export the DB is an open issue! https://github.com/wagtail/wagtail/issues/5464
# Excluded:
# wagtailcore.Revision

if [ $? -ne 0 ]; then
   echo ">>>./manage.py dumpdata<<< ist fehlgeschlagen. Beende das Skript."
   exit 1
fi

/usr/bin/borg create --stats -p --list --compression auto,lzma,9 ${REPOSITORY}::$(date +%Y_%m_%d-%H_%M) /app/ -e /app/static

if [ $? -ne 0 ]; then
   echo "Borg create ist fehlgeschlagen. Beende das Skript."
   exit 1
fi

# Remove old backup
/usr/bin/borg prune -v --list $REPOSITORY --keep-within=10d --keep-daily=180 --keep-weekly=52 --keep-monthly=-1