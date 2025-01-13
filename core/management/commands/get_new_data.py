from asgiref.sync import async_to_sync, sync_to_async
from django.core.management.base import BaseCommand
from django.conf import settings

from core.tools import (
    time,
    get_latest_boxes_with_distance_as_df,
    get_timeframe,
    run_multithreaded,
    write_to_influx,
    datetime, get_url,
)

import asyncio


class Command(BaseCommand):
    help = 'Import new data from senseBoxes'

    # def add_arguments(self, parser):
    #     parser.add_argument('--csv', type=str)

    def handle(self, *args, **options):

        start_timer = time.time()

        # this df contains only data fron "today" no further checks needed
        df = get_latest_boxes_with_distance_as_df()

        timeframe = get_timeframe()
        print(f"timeframe: {timeframe}")

        """
        ToDo: split up this job for every location?
        """
        # return a list of df
        results_list = asyncio.run(run_multithreaded(df, timeframe))

        for df in results_list:

            if df.empty:
                print(f">>>>>>>>>>>>>>>> senseBox has errors {df.attrs['box_id']} - {df.attrs['box_name']}")
            else:
                # print(f"dtype index: {df.index.dtype}")
                if write_to_influx(sensebox_id=df.attrs['box_id'], df=df):
                    print(f"Import complete for {df.attrs['box_id']} - {df.attrs['box_name']}")
                else:
                    print(f">>>>>>>>>>>>>>>> Import not succeed for {df.attrs['box_id']} - {df.attrs['box_name']}")

        print(f"Time elapsed: {time.time() - start_timer}")
        print(datetime.now())

        """
        Regenerate cache
        """

        if settings.DEBUG:
            #domain = "http://0.0.0.0:8000/"
            print("Debug mode on: no regeneration of cache")
        else:
            domain = settings.WAGTAILADMIN_BASE_URL + '/'

            print("regenerate cache ...")
            cache_list = ['draw_hexmap/temp', 'draw_hexmap/dust', 'erfrischungskarte/14Uhr', 'erfrischungskarte/9Uhr', 'erfrischungskarte/21Uhr']

            for url in cache_list:
                r = get_url(domain + url, headers={'not_valid': 'just to provide a header'})
                if r:
                    print(f'got response from {domain + url}')
                else:
                    print(f'failed to get response from {domain + url}')

            print(f"Time elapsed: {time.time() - start_timer}")

