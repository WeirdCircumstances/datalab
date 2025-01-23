import asyncio
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple

import httpx
import influxdb_client
import pandas as pd
import requests
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from influxdb_client.client.write_api import SYNCHRONOUS
from requests.adapters import HTTPAdapter
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from urllib3.util import Retry

from home.models import SenseBoxTable, SenseBoxLocation, GroupTag

# from multiprocessing.pool import ThreadPool

# INFLUX settings
influx_url = settings.INFLUX_URL
influx_token = settings.INFLUX_TOKEN
influx_org = settings.INFLUX_ORG
influx_bucket = settings.INFLUX_BUCKET

mapbox_token = settings.MAPBOX_TOKEN

# Retry-Logik mit Tenacity
@retry(stop=stop_after_attempt(2), wait=wait_fixed(0.5), retry=retry_if_exception_type(httpx.RequestError))
async def get_url_async(url: str, headers=None) -> httpx.Response:
    if headers is None:
        headers = {'Accept': 'application/json'}

    async with httpx.AsyncClient() as client:
        try:
            # print(f"try to get {url}")
            response = await client.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raises an HTTPStatusError if the response status code is 4xx, 5xx
            return response
        except httpx.HTTPStatusError as exc:
            print(f"HTTP error for {url}: {exc.response.status_code}")
            raise
        except httpx.RequestError as exc:
            print(f"Request error for {url}: {exc}")
            raise

retry = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
adapter = HTTPAdapter(max_retries=retry)
session = requests.Session()
session.mount('https://', adapter)

def get_url(url: str, headers=None) -> requests.Response:
    # ToDo: error handling (invalid url), show a response to the enduser
    if headers is None:
        headers = {'Accept': 'application/json'}
    try:
        print(f"try to get {url}")
        r = session.get(url, timeout=180, headers=headers)
        return r
    except Exception as e:
        print(f":::::::::::::::::::::::::::::::::::::: url did nothing return: {url} (Exception next line)")
        print(e)


def get_boxes_with_tag(tagname: str) -> pd.DataFrame:
    # cache_key = tagname['grouptag'].replace(' ', '')
    #
    # if cache.get(cache_key) is not None:
    #     # print('got tagname from cache')
    #     return cache.get(cache_key)
    # else:
    #     # print(f"Boxes tag: {tagname}")
    #     encoded_params = urllib.parse.urlencode(tagname)
    #     # https://docs.opensensemap.org/#api-Measurements-getDataByGroupTag
    #     # will change to /boxes/data?grouptag=:grouptag
    #     url = 'https://api.opensensemap.org/boxes/data/bytag' + '?' + encoded_params
    #
    #     # print(f"url: {url}")
    #
    #     r = get_url(url)
    #
    #     r_json = r.json()
    #
    #     # print(f"r_json: {r_json}")
    #     df = pd.DataFrame(r_json)
    #
    #     # df['grouptag'] = df['grouptag'].apply(json.loads)
    #
    #     cache.set(cache_key, df, 60 * 60)
    #     # print('set tagname in cache')
    boxes_with_tag = SenseBoxTable.objects.filter(grouptags__tag=tagname)

    boxes_with_tag_list = boxes_with_tag.values()

    df = pd.DataFrame(boxes_with_tag_list)

    print(f"df filtered for {tagname} \n {df.head()}")

    return df


def get_box_with_sensor_id(box_id: str, sensor_id: str) -> dict:
    url = f"https://api.opensensemap.org/boxes/{box_id}/sensors/{sensor_id}"
    r = get_url(url)

    r_json = r.json()
    return r_json


async def get_sensor_data(df: pd.DataFrame, sensor_id: str) -> dict | None:
    print(":::::::::::::::::::::::::::::::::::::: get_sensor_data from tools!")

    # consumes a df with a sensorID column
    # returns a sensor dict
    # print(f'Search for sensor id: {sensor_id}')

    # find first box with this sensor ID
    result = df[df['sensorId'] == sensor_id]
    box_id = result['boxId'].iloc[0]

    # get box with all sensors

    url = f'https://api.opensensemap.org/boxes/{box_id}'
    box = await get_url_async(url)
    box = box.json()

    # print(box)

    for sensor in box['sensors']:
        if sensor_id == sensor['_id']:
            # print(f'Found {sensor_id} - {sensor["title"]}')
            sensor['grouptag'] = box['grouptag']
            sensor['name'] = box['name']
            sensor['lat'] = box['currentLocation']['coordinates'][1]
            sensor['lon'] = box['currentLocation']['coordinates'][0]
            return sensor
    return None


async def get_boxes_with_distance(params: dict) -> dict:
    # example: box_json = get_boxes_with_distance({'near': '13.3992,52.516221', 'maxDistance': '10000', 'exposure': 'outdoor', })
    encoded_params = urllib.parse.urlencode(params)

    url = 'https://api.opensensemap.org/boxes' + '?' + encoded_params

    r = await get_url_async(url)

    r_json = r.json()
    return r_json


async def get_latest_boxes_with_distance_as_df(region: str = 'all', cache_time = 60) -> pd.DataFrame:

    cache_key = f"latest_boxes_{region}"

    df = cache.get(cache_key)
    if df is not None:
        print(f"cache hit for {cache_key}")
        return df

    else:
        print(f"cache miss for {cache_key}")
        async def create_df(_frames, _location):
            print(f'get location: {location.name}')
            # near order: lon, lat

            lon = _location.location_longitude
            lat = _location.location_latitude
            distance = _location.maxDistance
            exposure = _location.exposure

            params = {'near': f'{lon}, {lat}', 'maxDistance': f'{distance}', 'exposure': exposure}
            # print(params)

            box_json = await get_boxes_with_distance(params)
            temp_df = pd.DataFrame(box_json)

            _frames.append(temp_df)
            return _frames

        frames = []

        if region == 'all':
            async for location in SenseBoxLocation.objects.all():
                frames = await create_df(frames, location)
        else:
            async for location in SenseBoxLocation.objects.filter(name=region):
                frames = await create_df(frames, location)

        if len(frames) == 0:
            print(':::::::::::::::::::::::::::::::::::::::: No locations found! - Frame len is 0')
            raise

        df = pd.concat(frames)

        #
        df['lastMeasurementAt'] = pd.to_datetime(df['lastMeasurementAt'], format='%Y-%m-%dT%H:%M:%S.%fZ')

        # Remove all NaT
        df = df.dropna(subset=['lastMeasurementAt'])

        # remove seconds -> data becomes comparable
        df['lastMeasurementAt'] = df['lastMeasurementAt'].dt.floor('Min')

        # most recent date
        most_recent_date = df['lastMeasurementAt'].max()
        # get the latest date
        start_time = most_recent_date.date()
        # set the index to this tmie series
        df = df.set_index('lastMeasurementAt')
        # keep only values from this date
        df = df[(df.index.date >= start_time)]

    cache.set(cache_key, df, timeout=int(cache_time))

    return df


def write_to_influx(sensebox_id: str, df: pd.DataFrame) -> bool:
    df.dropna(how='any', inplace=True)

    write_client = influxdb_client.InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    write_api = write_client.write_api(write_options=SYNCHRONOUS)
    write_api.write(influx_bucket, record=df, data_frame_measurement_name=sensebox_id)
    return True


async def get_timeframe(time_delta: float = 1.0) -> str:
    ##########################################################
    # get correct time delta and timezone
    ##########################################################

    # Get the current UTC time and convert it to the local timezone
    local_time = datetime.now(timezone.utc).astimezone()

    # get the date from today - timedelta. Interpret the resulting string as time and isoformat
    dt = (local_time.replace(second=0, microsecond=0) - timedelta(days=time_delta)).astimezone().isoformat()  # .replace('+02:00','') + 'Z'
    # last_month = dt #.replace(hour=0, minute=0, second=0, microsecond=0)

    # the url parameter can not parse the value, when a + sign is in the string, so the function will split the string into three
    head, sep, tail = dt.partition('+')

    # appends a Z for the military timezone Zulu, the url paramter want it this way
    delta = head + 'Z'

    # print(f":::::::::::::::::::::::::::::::::::::: DELTA: {delta}")

    return delta


async def get_sensebox_data(box: pd.Series, timeframe: str) -> pd.DataFrame:
    ##########################################################
    # box comes as series -> new df with data from all sensors is created
    # 22 sec for emtpy table
    ##########################################################

    box_df = pd.DataFrame()  # create it empty and fill it with coordinates (location) and sensor data

    box_name = box['name']
    box_id = box['_id']
    coordinates = box['currentLocation']['coordinates']
    grouptags = box['grouptag']

    # Attention! dataframe attr is experimental: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.attrs.html#pandas.DataFrame.attrs
    # "pandas.concat copies attrs only if all input datasets have the same attrs."
    box_df.attrs['box_id'] = box_id
    box_df.attrs['box_name'] = box_name

    # if any error happen here, a solution is in the part with GroupTag
    sensebox_entry, created = await SenseBoxTable.objects.aupdate_or_create(sensebox_id=box_id)

    if created:
        try:
            if sensebox_entry.location_latitude:
                # print('Coordinates existing')
                pass
            else:
                print(f'Writing coordinates: [{coordinates[1]} , {coordinates[0]}]')
                sensebox_entry.location_latitude = coordinates[1]
                sensebox_entry.location_longitude = coordinates[0]
                # sensebox_entry.save()
            if sensebox_entry.name:
                pass
            else:
                print(f'Writing name: {box_name}')
                sensebox_entry.name = box_name
                # sensebox_entry.save()
        except Exception as e:
            print(f'SenseBox was not found in DB. Check >get_new_data.py< error: {e}')
            pass

        # some work to create grouptags in a parallel environment
        # see also in the modell for GroupTag
        if isinstance(grouptags, list):
            for item in grouptags:
                if item != '' or item == ' ':
                    # comments are the sync call - this funct is now async
                    #try:
                    #    with transaction.atomic():
                    #        tag, tag_created = await GroupTag.objects.aupdate_or_create(tag=item)
                    #except IntegrityError:
                    #    tag = await GroupTag.objects.aget(tag=item)
                    tag, tag_created = await GroupTag.objects.aupdate_or_create(tag=item)
                    #sensebox_entry.grouptags.add(tag)
                    await sync_to_async(sensebox_entry.grouptags.add)(tag)
                    print(f"added tag {tag} to box {box_name}")

        await sensebox_entry.asave()  # have some mercy to postgres and save only once

    for p in box['sensors']:
        # print(f"All sensor {p}")

        if p['title'] == 'Temperature':
            p['title'] = 'Temperatur'
            print('Changed "Temperature" to "Temperatur"')
        title = p['title']
        sensor_id = p['_id']

        # get sensor and create df
        url = f'https://api.opensensemap.org/boxes/{box_id}/data/{sensor_id}?format=json&from-date={timeframe}'
        r_sensor = await get_url_async(url)
        r_sensor_json = r_sensor.json()
        sensor_df = pd.DataFrame.from_dict(r_sensor_json)

        # print(f"sensor columns: {sensor_df.columns}")

        if 'value' in sensor_df.columns:
            box_df[title] = sensor_df['value'].astype(float)  # pydantic?
            box_df['createdAt'] = sensor_df['createdAt']

    ##########################################################
    # Transform data
    ##########################################################

    box_df['createdAt'] = pd.to_datetime(box_df['createdAt'], format='%Y-%m-%dT%H:%M:%S.%fZ')
    box_df['createdAt'] = box_df['createdAt'].dt.floor('Min')

    # box_df['createdAt'] = box_df['createdAt'].dt.tz_convert(tz='Europe/Berlin')

    # set the time to index, InfluxDB need it this way
    box_df = box_df.set_index('createdAt')

    if box_df.empty:
        print(f"************************** SB got nothing back: {box_name}")

    if box_df.index.name != 'createdAt':
        print(f":::::::::::::::::::::::::::::::::::::: box_df needs 'createdAt' as index name: {box_df.head()}")
        raise

    print(f"Got: {box_name}")
    # print(box_df.columns)
    # print(box_df.head())

    return box_df


async def run_multithreaded(df: pd.DataFrame, timeframe: str) -> list[pd.DataFrame]:
    args = [(box, timeframe) for index, box in df.iterrows()]
    tasks = [get_sensebox_data(*arg) for arg in args]
    return await asyncio.gather(*tasks)


async def fetch_tile(url, cache_timeout=60 * 60 * 24):  # set cache 24 h
    # check if tile is in cache
    cached_response = await cache.aget(url)
    if cached_response:
        print(f"Fetched {url} from cache")
        return cached_response

    # aks for tile, when not in cache
    response = await get_url_async(url=url, headers={"User-Agent": f"DataLab/1.0 (https://www.humboldt-explorers.de/; {settings.CONTACT_EMAIL})"})

    if response.status_code == 200:
        # save answer in cache
        await cache.aset(url, response.content, cache_timeout)
        return response.content
    else:
        # error handling and logging
        print(f"Error getting {url}")
        response.raise_for_status()


def calculate_centroid(coordinates: List[Dict[str, float]]) -> Tuple[str, str]:
    if len(coordinates) == 0:
        print('Empty coordinates!')
        return '52.516221', '13.3992'  # the "normal" center I use everywhere

    # Durchschnitt der Breitengrade (Latitude) und Längengrade (Longitude)
    latitudes = [coord['lat'] for coord in coordinates]
    longitudes = [coord['lon'] for coord in coordinates]

    centroid_lat = sum(latitudes) / len(latitudes)
    centroid_lon = sum(longitudes) / len(longitudes)

    centroid_lat = str(round(centroid_lat, 6)).replace(',','.')
    centroid_lon = str(round(centroid_lon, 6)).replace(',','.')

    return centroid_lat, centroid_lon
