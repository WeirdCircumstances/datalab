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
from home.models import SenseBoxTable


class Command(BaseCommand):
    help = "Collect new data from senseBoxes"

    def add_arguments(self, parser):
        parser.add_argument('-t', type=float, help="Time delta to collect data")

    def handle(self, *args, **options):

        if options["t"]:
            time_delta = options["t"]
        else:
            time_delta = 0.0

        print(f"Time delta: {time_delta}")

        start_timer = time.time()

        # this df contains only data fron "today" no further checks needed
        df = asyncio.run(get_latest_boxes_with_distance_as_df())

        print(f"get_latest_boxes_with_distance_as_df: {time.time() - start_timer}")

        # Any value between 0.1 and 3.0 (3 days) can be selected. Even higher numbers are possible, but are very ressource intensive for the senseBox API.
        # Default should be 0.0. This means, data is collected until midnight. Selecting other values between 0 and 1 does not save anything, as it seems.
        timeframe = asyncio.run(get_timeframe(time_delta=time_delta)) # 0.0 collects data for this day, until midnight.
        print(f"timeframe: {timeframe}")

        """
        ToDo: split up this job for every location?
        """
        # return a list of df
        results_list = asyncio.run(run_multithreaded(df, timeframe))

        for df in results_list:

            if df.empty:
                print(f"Empty df: {df.attrs['box_id']} - {df.attrs['box_name']}")
            else:
                # print(f"dtype index: {df.index.dtype}")
                if write_to_influx(sensebox_id=df.attrs["box_id"], df=df):
                    print(f"Import complete for {df.attrs['box_id']} - {df.attrs['box_name']}")
                else:
                    print(f">>>>>>>>>>>>>>>> Import not succeed for {df.attrs['box_id']} - {df.attrs['box_name']}")


        # check SenseBox Table fpr errors and fix them
        all_boxes = SenseBoxTable.objects.all()
        for box in all_boxes:
            if box.location_latitude is None:
                print(f"Missing location, delete box: {box.sensebox_id}")
                box.delete()

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
                "erfrischungskarte/9Uhr/",
                "erfrischungskarte/10Uhr/",
                "erfrischungskarte/11Uhr/",
                "erfrischungskarte/12Uhr/",
                "erfrischungskarte/13Uhr/",
                "erfrischungskarte/14Uhr/",
                "erfrischungskarte/15Uhr/",
                "erfrischungskarte/16Uhr/",
                "erfrischungskarte/17Uhr/",
                "erfrischungskarte/18Uhr/",
                "erfrischungskarte/19Uhr/",
                "erfrischungskarte/20Uhr/",
                "erfrischungskarte/21Uhr/",
            ]

            # single graphics
            cache_list += [
                # "s/hexmap?ressource_path=Temperatur",
                # "s/hexmap?ressource_path=PM10",
                # "s/hexmap?ressource_path=PM2.5",
                "s/erfrischungskarte/9Uhr/",
                "s/erfrischungskarte/10Uhr",
                "s/erfrischungskarte/11Uhr",
                "s/erfrischungskarte/12Uhr",
                "s/erfrischungskarte/13Uhr",
                "s/erfrischungskarte/14Uhr/",
                "s/erfrischungskarte/15Uhr/",
                "s/erfrischungskarte/16Uhr",
                "s/erfrischungskarte/17Uhr",
                "s/erfrischungskarte/18Uhr",
                "s/erfrischungskarte/19Uhr",
                "s/erfrischungskarte/20Uhr",
                "s/erfrischungskarte/21Uhr/",
            ]

            for url in cache_list:
                r = get_url(domain + url)
                if r:
                    print(f"+++ success: {domain + url}")
                else:
                    print(f"--- failed to get response from: {domain + url}")

            print(f"Time elapsed: {time.time() - start_timer}")
