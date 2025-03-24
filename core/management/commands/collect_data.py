import asyncio
import time

from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand

from core.tools import (
    datetime,
    get_latest_boxes_with_distance_as_df,
    get_timeframe,
    get_url,
    run_multithreaded,
    write_to_influx,
)


class Command(BaseCommand):
    help = "Import new data from senseBoxes"

    # def add_arguments(self, parser):
    #     parser.add_argument('--csv', type=str)

    def handle(self, *args, **options):

        start_timer = time.time()

        # this df contains only data fron "today" no further checks needed
        df = asyncio.run(get_latest_boxes_with_distance_as_df())

        timeframe = asyncio.run(get_timeframe(time_delta=0.0))
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
                if write_to_influx(sensebox_id=df.attrs["box_id"], df=df):
                    print(f"Import complete for {df.attrs['box_id']} - {df.attrs['box_name']}")
                else:
                    print(f">>>>>>>>>>>>>>>> Import not succeed for {df.attrs['box_id']} - {df.attrs['box_name']}")


        print(results_list[60].shape)
        print(f"Time elapsed: {time.time() - start_timer}")
        print(datetime.now())

        """
        Regenerate cache
        """

        print(f">>>>>>>>>> cache backend: {caches['default']}")

        if settings.DEBUG:
            print("Debug mode on: no regeneration of cache")
        else:
            domain = settings.WAGTAILADMIN_BASE_URL + "/"

            print("regenerate cache ...")
            cache_list = [
                "hexmap?ressource_path=Temperatur",
                "hexmap?ressource_path=PM10&colorscale=GnBu",
                # "hexmap?ressource_path=PM2.5",
                "erfrischungskarte/14Uhr/",
                "erfrischungskarte/9Uhr/",
                "erfrischungskarte/21Uhr/",
            ]

            # single graphics
            cache_list += [
                # "s/hexmap?ressource_path=Temperatur",
                # "s/hexmap?ressource_path=PM10",
                # "s/hexmap?ressource_path=PM2.5",
                "s/erfrischungskarte/9Uhr/",
                # "s/erfrischungskarte/10Uhr",
                # "s/erfrischungskarte/11Uhr",
                # "s/erfrischungskarte/12Uhr",
                # "s/erfrischungskarte/13Uhr",
                "s/erfrischungskarte/14Uhr/",
                "s/erfrischungskarte/15Uhr/",
                # "s/erfrischungskarte/16Uhr",
                # "s/erfrischungskarte/17Uhr",
                # "s/erfrischungskarte/18Uhr",
                # "s/erfrischungskarte/19Uhr",
                # "s/erfrischungskarte/20Uhr",
                "s/erfrischungskarte/21Uhr/",
            ]

            for url in cache_list:
                r = get_url(domain + url)
                if r:
                    print(f"+++ success: {domain + url}")
                else:
                    print(f"--- failed to get response from: {domain + url}")

            print(f"Time elapsed: {time.time() - start_timer}")
