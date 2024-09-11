#!/bin/sh

# ./dbbackup.sh

# use this to create a working backup version
# python ./repair_json_revision.py

HOST=oc
APP=sensebox

rsync -uvPzEcha --exclude-from=exclude_list.txt --stats . $HOST:~/$APP

# shellcheck disable=SC2087
ssh $HOST <<EOF
 cd $APP
        # sudo docker exec -t $(docker ps -qf name=sensebox) ./manage.py dumpdata --natural-foreign --indent 2 -e auth.permission -e contenttypes -e wagtailcore.groupcollectionpermission -e wagtailcore.grouppagepermission -e sessions -e wagtailimages.rendition -o ./dump.json

 sudo docker compose -f compose-production.yml stop

 sudo docker compose -f compose-production.yml pull db caddy

 sudo docker compose -f compose-production.yml build sensebox

 sudo docker compose -f compose-production.yml up

 # sudo docker compose -f compose-production.yml restart

EOF
