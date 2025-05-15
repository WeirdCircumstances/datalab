#!/bin/sh

HOST=oc
APP=datalab

rsync -uvPzEcha --exclude-from=exclude_list.txt --stats . $HOST:~/$APP

# shellcheck disable=SC2087
ssh $HOST <<EOF
 cd $APP
        # sudo docker exec -t $(docker ps -qf name=datalab) ./manage.py dumpdata --natural-foreign --indent 2 -e auth.permission -e contenttypes -e wagtailcore.groupcollectionpermission -e wagtailcore.grouppagepermission -e sessions -e wagtailimages.rendition -o ./dump.json

 sudo docker compose -f compose-production.yml stop

 sudo docker compose -f compose-production.yml pull db caddy

 sudo docker rm datalab-datalab-1
 sudo docker compose -f compose-production.yml build datalab

 sudo docker compose -f compose-production.yml up #-d

        # sudo docker compose -f compose-production.yml restart
EOF
