from asgiref.sync import async_to_sync
from celery import shared_task

from core.tools import get_latest_boxes_with_distance_as_df


@shared_task()
def latest_boxes_as_df(region: str = "all", cache_time=60):
    return async_to_sync(get_latest_boxes_with_distance_as_df)(region, cache_time)
