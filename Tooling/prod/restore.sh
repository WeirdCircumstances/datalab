#!/bin/bash

mkdir /app/restored
cd /app/restored
borg extract ${REPOSITORY}::$(borg list --short ${REPOSITORY} | tail -n 1)

# ./manage.py shell
# from wagtail.models import Page
# Page.objects.all().delete()