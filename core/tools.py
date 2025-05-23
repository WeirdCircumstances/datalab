import asyncio
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple

import httpx
import influxdb_client
import math
import numpy as np
import pandas as pd
import plotly
import plotly.graph_objects as go
import requests
from asgiref.sync import sync_to_async, async_to_sync
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import MultipleObjectsReturned
from influxdb_client.client.write_api import SYNCHRONOUS
from requests.adapters import HTTPAdapter
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from urllib3.util import Retry

from home.models import SenseBoxTable, SenseBoxLocation, GroupTag, SensorsInfoTable

# from multiprocessing.pool import ThreadPool

# INFLUX settings
influx_url = settings.INFLUX_URL
influx_token = settings.INFLUX_TOKEN
influx_org = settings.INFLUX_ORG
influx_bucket = settings.INFLUX_BUCKET

mapbox_token = settings.MAPBOX_TOKEN


# Retry-Logik mit Tenacity
@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(0.5),
    retry=retry_if_exception_type(httpx.RequestError),
)

@shared_task()
def get_url_task(url: str, headers=None):
    return async_to_sync(get_url_async)(url, headers)


async def get_url_async(url: str, headers=None) -> httpx.Response | None:
    if headers is None:
        headers = {"Accept": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            # print(f"try to get {url}")
            response = await client.get(url, headers=headers, timeout=10)
            # response.raise_for_status()  # Raises an HTTPStatusError if the response status code is 4xx, 5xx
            return response
        except httpx.HTTPStatusError as exc:
            print(f">>>>>>>> HTTP error for {url}: {exc.response.status_code}")
            raise
        except httpx.RequestError as exc:
            print(f">>>>>>>> Request error for {url}: {exc}")
            raise
        except httpx.ReadTimeout as exc:
            print(f">>>>>>>> Request error for {url}: {exc}")
            return httpx.Response(status_code=500, content=b"")
        except httpx.ConnectTimeout as exc:
            print(f">>>>>>>> Request error for {url}: {exc}")
            return None # httpx.Response(status_code=500, content=b"")


retry = Retry(
    total=2,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry)
session = requests.Session()
session.mount("https://", adapter)


def get_url(url: str, headers=None) -> requests.Response | None:
    # ToDo: error handling (invalid url), show a response to the enduser
    if headers is None:
        headers = {"Accept": "application/json"}
    try:
        print(f"try to get {url}")
        r = session.get(url, timeout=180, headers=headers)
        return r
    except Exception as e:
        print(f":::::::::::::::::::::::::::::::::::::: url did nothing return: {url} (Exception next line)")
        print(e)


def get_boxes_with_tag(tagname: str) -> pd.DataFrame:
    # ToDo: is this still used?
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
    # ToDo: check if there is any use of this function
    print(":::::::::::::::::::::::::::::::::::::: get_sensor_data from tools!")

    # consumes a df with a sensorID column
    # returns a sensor dict
    # print(f'Search for sensor id: {sensor_id}')

    # find first box with this sensor ID
    result = df[df["sensorId"] == sensor_id]
    box_id = result["boxId"].iloc[0]

    # get box with all sensors

    url = f"https://api.opensensemap.org/boxes/{box_id}"
    box = await get_url_async(url)
    box = box.json()

    for sensor in box["sensors"]:
        if sensor_id == sensor["_id"]:
            # print(f'Found {sensor_id} - {sensor["title"]}')
            sensor["grouptag"] = box["grouptag"]
            sensor["name"] = box["name"]
            sensor["lat"] = box["currentLocation"]["coordinates"][1]
            sensor["lon"] = box["currentLocation"]["coordinates"][0]
            return sensor
    return None


async def get_boxes_with_distance(params: dict) -> dict:
    # example: box_json = get_boxes_with_distance({'near': '13.3992,52.516221', 'maxDistance': '10000', 'exposure': 'outdoor', })
    encoded_params = urllib.parse.urlencode(params)

    url = "https://api.opensensemap.org/boxes" + "?" + encoded_params

    r = await get_url_async(url)

    if r is None:
        print("------------- ConnectTimeout: No response from url")
        return {}

    r_json = r.json()
    return r_json


async def get_latest_boxes_with_distance_as_df(region: str = "all", cache_time=60) -> pd.DataFrame:

    cache_key = f"latest_boxes_{region}"

    df = cache.get(cache_key)
    if df is not None:
        #print(f"cache hit for single box {cache_key}")
        return df

    else:
        print(f"cache miss for {cache_key}")

        async def create_df(_frames, _location):
            print(f"get location: {location.name}")
            # near order: lon, lat

            lon = _location.location_longitude
            lat = _location.location_latitude
            distance = _location.maxDistance
            exposure = _location.exposure

            params = {
                "near": f"{lon}, {lat}",
                "maxDistance": f"{distance}",
                "exposure": exposure,
            }
            # print(params)

            box_json = await get_boxes_with_distance(params)
            temp_df = pd.DataFrame(box_json)

            _frames.append(temp_df)
            return _frames

        frames = []

        if region == "all":
            async for location in SenseBoxLocation.objects.all():
                frames = await create_df(frames, location)
        else:
            async for location in SenseBoxLocation.objects.filter(name=region):
                frames = await create_df(frames, location)

        if len(frames) == 0:
            print("No locations found! - Frame len is 0")
            raise

        df = pd.concat(frames)

        #
        df["lastMeasurementAt"] = pd.to_datetime(df["lastMeasurementAt"], format="%Y-%m-%dT%H:%M:%S.%fZ")

        # Remove all NaT
        df = df.dropna(subset=["lastMeasurementAt"])

        # remove seconds -> data becomes comparable
        df["lastMeasurementAt"] = df["lastMeasurementAt"].dt.floor("Min")
        # calc mean of the aggregated values NOT POSSIBLE -> columns contains non-numeric values
        # df = df.groupby("lastMeasurementAt", as_index=False).mean()

        # most recent date
        most_recent_date = df["lastMeasurementAt"].max()
        # get the latest date
        start_time = most_recent_date.date()
        # set the index to this tmie series
        df = df.set_index("lastMeasurementAt")
        # keep only values from this date
        df = df[(df.index.date >= start_time)]

    cache.set(cache_key, df, timeout=int(cache_time))

    return df


def write_to_influx(sensebox_id: str, df: pd.DataFrame) -> bool:
    df.dropna(how="any", inplace=True)

    write_client = influxdb_client.InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    write_api = write_client.write_api(write_options=SYNCHRONOUS)
    write_api.write(influx_bucket, record=df, data_frame_measurement_name=sensebox_id)
    return True


async def get_timeframe(time_delta: float = 0.0) -> str:
    ##########################################################
    # get correct time delta and timezone
    ##########################################################

    # Get the current UTC time and convert it to the local timezone
    local_time = datetime.now(timezone.utc).astimezone()


    if time_delta == 0.0:
        dt = local_time.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    else:
        # get the date from today - timedelta. Interpret the resulting string as time and isoformat
        dt = (
            (local_time.replace(second=0, microsecond=0) - timedelta(days=time_delta)).astimezone().isoformat()
        )  # .replace('+02:00','') + 'Z'
        # last_month = dt #.replace(hour=0, minute=0, second=0, microsecond=0)

    # the url parameter can not parse the value, when a + sign is in the string, so the function will split the string into three
    head, sep, tail = dt.partition("+")

    # appends a Z for the military timezone Zulu, the url paramter want it this way
    delta = head + "Z"

    # print(f":::::::::::::::::::::::::::::::::::::: DELTA: {delta}")

    return delta


def seconds_until_next_hour() -> int:
    """return seconds until next hour"""
    now = datetime.now()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return int((next_hour - now).total_seconds())


async def get_sensebox_data(box: pd.Series, timeframe: str) -> pd.DataFrame:
    ##########################################################
    # box comes as series -> new df with data from all sensors is created
    # 22 sec for emtpy table
    ##########################################################

    box_df = pd.DataFrame()  # create it empty and fill it with coordinates (location) and sensor data

    box_name = box["name"]
    box_id = box["_id"]
    coordinates = box["currentLocation"]["coordinates"]
    grouptags = box["grouptag"]

    # Attention! dataframe attr is experimental: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.attrs.html#pandas.DataFrame.attrs
    # "pandas.concat copies attrs only if all input datasets have the same attrs."
    box_df.attrs["box_id"] = box_id
    box_df.attrs["box_name"] = box_name

    try:
        # if any error happen here, a solution is in the part with GroupTag
        sensebox_entry, created = await SenseBoxTable.objects.aupdate_or_create(sensebox_id=box_id)
    except SenseBoxTable.MultipleObjectsReturned:
        print(f"Multiple entries found for {box_name}")
        await SenseBoxTable.objects.filter(sensebox_id=box_id).adelete()
        sensebox_entry, created = await SenseBoxTable.objects.aupdate_or_create(sensebox_id=box_id)

    if created:
        try:
            if sensebox_entry.location_latitude:
                # print('Coordinates existing')
                pass
            else:
                print(f"Writing coordinates: [{coordinates[1]} , {coordinates[0]}]")
                sensebox_entry.location_latitude = coordinates[1]
                sensebox_entry.location_longitude = coordinates[0]
                # sensebox_entry.save()
            if sensebox_entry.name:
                pass
            else:
                print(f"Writing name: {box_name}")
                sensebox_entry.name = box_name
                # sensebox_entry.save()
        except Exception as e:
            print(f"SenseBox was not found in DB. Check >get_new_data.py< error: {e}")
            pass

        # some work to create grouptags in a parallel environment
        # see also in the modell for GroupTag
        if isinstance(grouptags, list):
            for item in grouptags:
                if item != "" or item == " ":
                    # comments are the sync call - this funct is now async
                    # try:
                    #    with transaction.atomic():
                    #        tag, tag_created = await GroupTag.objects.aupdate_or_create(tag=item)
                    # except IntegrityError:
                    #    tag = await GroupTag.objects.aget(tag=item)
                    tag, tag_created = await GroupTag.objects.aupdate_or_create(tag=item)
                    # sensebox_entry.grouptags.add(tag)
                    await sync_to_async(sensebox_entry.grouptags.add)(tag)
                    print(f"added tag {tag} to box {box_name}")

        await sensebox_entry.asave()  # have some mercy to postgres and save only once

    uniform_spelling_list = [
        ["Temperatur", "Temperature", "Lufttemperatur", "Temperature (DHT11)", "temperature", "°C"],
        [
            "Luftfeuchtigkeit",
            "Luftfeuchte",
            "rel. Luftfeuchte",
            "Humidity (DHT11)",
            "Humidity",
            "humidity",
            "Moisture",
            "%",
        ],
        ["Luftdruck", "atm. Luftdruck", "pressure", "hPa"],
        ["PM10", "Staub 10µm", "pm10", "particle PM10", "µg/m³"],
        ["PM2.5", "Staub 2.5µm", "pm2.5", "particle PM2.5", "µg/m³"],
        ["Beleuchtungsstärke", "Beleuchtungsastärke", "lx"],
        ["UV-Intensität", "μW/cm²"],
        ["CO₂", "CO2", "ppm"],
        ["Lautstärke", "dB"],
    ]

    for p in box["sensors"]:
        # print(f"All sensor {p}")

        for this_list in uniform_spelling_list:
            if p["title"] in this_list:  # and p["title"] != this_list[0]:
                # print(f'Changed {p["title"]} to {this_list[0]}, unit {this_list[-1]}')
                p["title"] = this_list[0]
                p["unit"] = this_list[-1]

        title = p["title"]
        sensor_id = p["_id"]
        unit = p["unit"]

        # await SensorsInfoTable.objects.aget_or_create(name=title, unit=unit)

        try:
            await SensorsInfoTable.objects.aget_or_create(name=title, unit=unit)
        except MultipleObjectsReturned:
            # delete all
            await SensorsInfoTable.objects.filter(name=title, unit=unit).adelete()
            # create new ...
            await SensorsInfoTable.objects.acreate(name=title, unit=unit)

        # get sensor and create df
        url = f"https://api.opensensemap.org/boxes/{box_id}/data/{sensor_id}?format=json&from-date={timeframe}"
        r_sensor = await get_url_async(url)
        r_sensor_json = r_sensor.json()
        sensor_df = pd.DataFrame.from_dict(r_sensor_json)

        # print(f"sensor columns: {sensor_df.columns}")

        if "value" in sensor_df.columns:
            box_df[title] = sensor_df["value"].astype(float)  # pydantic?
            box_df["createdAt"] = sensor_df["createdAt"]

    ##########################################################
    # Transform data
    ##########################################################

    try:
        box_df["createdAt"] = pd.to_datetime(box_df["createdAt"], format="%Y-%m-%dT%H:%M:%S.%fZ")
    except KeyError as e:
        print(f"KeyError: {e}")
        print(f"Box {box_name} has no values in the selected timeframe. Returning empty df.")
        df = pd.DataFrame()
        df.attrs["box_id"] = box_id
        df.attrs["box_name"] = box_name
        return df
    box_df["createdAt"] = box_df["createdAt"].dt.floor("Min")

    # calc mean of the aggregated values
    box_df = box_df.groupby("createdAt", as_index=False).mean()

    # box_df['createdAt'] = box_df['createdAt'].dt.tz_convert(tz='Europe/Berlin')

    # set the time to index, InfluxDB need it this way
    box_df = box_df.set_index("createdAt")

    if box_df.empty:
        print(f"************************** SB got nothing back: {box_name}")

    if box_df.index.name != "createdAt":
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
    response = await get_url_async(
        url=url,
        headers={"User-Agent": f"DataLab/1.0 (https://www.humboldt-explorers.de/; {settings.CONTACT_EMAIL})"},
    )

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
        print("Empty coordinates!")
        return "52.516221", "13.3992"  # the "normal" center I use everywhere

    # Durchschnitt der Breitengrade (Latitude) und Längengrade (Longitude)
    latitudes = [coord["lat"] for coord in coordinates]
    longitudes = [coord["lon"] for coord in coordinates]

    centroid_lat = sum(latitudes) / len(latitudes)
    centroid_lon = sum(longitudes) / len(longitudes)

    centroid_lat = str(round(centroid_lat, 6)).replace(",", ".")
    centroid_lon = str(round(centroid_lon, 6)).replace(",", ".")

    return centroid_lat, centroid_lon


# function to render graph with the same settings every time
async def render_graph(fig, displaymodebar: bool = True) -> go.Figure:
    return plotly.offline.plot(
        fig,
        include_plotlyjs=False,
        output_type="div",
        # image_width='100%',
        # image_height='100%',
        auto_open=False,
        # https://plotly.com/python/configuration-options/
        config={
            "displayModeBar": displaymodebar,
            "displaylogo": False,
            "responsive": True,
            "modeBarButtonsToRemove": [
                "autoScale",
                "zoom",
                "pan",
                "toImage",
                "resetViewMapbox",
                "select",
                "toggleHover",
                "lasso2d",
                "pan2d",
                "select2d",
            ],
        },
    )


hexmap_style = [
    "basic",
    "open-street-map",
    "white-bg",
    "carto-positron",
    "carto-darkmatter",
    "outdoors",
    "light",
    "dark",
    "satellite",
    "satellite-streets",
]


# this function calculate from the distance in km, the distance in longitude
async def calculate_eastern_and_western_longitude(longitude, distance_km, latitude):
    longitude = float(longitude)
    distance_km = float(distance_km)
    latitude = float(latitude)
    earth_radius = 6371
    delta_longitude = distance_km / (math.cos(math.radians(latitude)) * (math.pi / 180) * earth_radius)
    eastern_longitude = longitude + delta_longitude
    western_longitude = longitude - delta_longitude
    return eastern_longitude, western_longitude


async def red_shape_creator(threshold: float, df: pd.DataFrame, item: str, row: int) -> List[Dict]:
    # draw a red box, when a threshold value is passed

    # Threshold: Grenzwert für das Kalenderjahr, Vergleich von PM2.5 PM10 dadurch möglich.
    # Bei PM10 darf der Grenzwert von 50 µg/qm in 24 h maximal 35 Mal pro Jahr überschritten werden
    # https://www.umweltbundesamt.de/daten/luft/feinstaub-belastung#bestandteile-des-feinstaubs

    if item == "title":  # this is the case, when showing "graph_by_tag"
        pm_values = df["value"]
        time_values = df["createdAt"]
    else:  # the "normal" situation, when showing "daw_graph"
        pm_values = df[item]
        time_values = df["_time"]

    above_threshold = pm_values >= threshold
    # the next lines does a lot!
    # - first we convert the list "above_threshold" from True & False to 0 & 1
    # - with np.diff we get all changes, so when a value changes for example from 0 to 1. When nothing changed, we will get a 0
    # - next, we get only the locations in the list, where a number except 0 is. Those are the values, we can use in df["_time"] (time_values), to start and stop a red box!
    # - last, we add 1 to this list, because we want to start the drawing of the red box, after the first value above, below the threshold and not before this point :)
    change_points = np.where(np.diff(above_threshold.astype(int)) != 0)[0] + 1

    # shapes is a list of dicts -> used to hold the values for the red boxes and dashed line
    shapes = []  # holds the red boxes
    ranges = []  # hold the timeframes for the red boxes

    # draw a red box, when ALL values are above threshold (happened with PM10 on 13.02.2025!)
    if pm_values.min(skipna=True) > threshold:
        print(f"ALL values are above threshold!!!: {pm_values.min(skipna=True)}")
        ranges.append((time_values.iloc[0], time_values.iloc[-1]))

    # check if any changepoint detected
    if len(change_points) > 0:
        # ranges is a list of time values, needed to start and stop the drawing of red boxes

        # check if the first reported value is above the threshold
        # if so, then we start to draw a box until the first value in the change_points list
        if above_threshold.iloc[0]:
            ranges.insert(0, (time_values.iloc[0], time_values.iloc[change_points[0]]))

            # skip only the first value in the change_points list. We have already used it in the function above.
            for i in range(1, len(change_points) - 1, 2):
                start = time_values.iloc[change_points[i]]  # start and stop of the red box
                end = time_values.iloc[change_points[i + 1]]
                ranges.append((start, end))
        else:
            # first value is below threshold
            # we start at the beginning with range(0)
            for i in range(0, len(change_points) - 1, 2):
                start = time_values.iloc[change_points[i]]
                end = time_values.iloc[change_points[i + 1]]
                ranges.append((start, end))

        # check if last value above threshold
        # then we draw a red box from the last reported point to the end
        if above_threshold.iloc[-1]:
            ranges.append((time_values.iloc[change_points[-1]], time_values.iloc[-1]))

    # the red box should fill the whole y-axis
    y_min = threshold  # pm_values.min()
    y_max = pm_values.max() + pm_values.max() / 10.0

    # instructions to draw red boxes for values above the threshold
    for x0, x1 in ranges:
        shapes.append(
            {
                "type": "rect",
                "x0": x0,
                "x1": x1,  # start and stop
                "y0": y_min,
                "y1": y_max,
                "fillcolor": "red",
                "opacity": 0.3,
                "layer": "above",  # above the grid in the background
                "xref": f"x{row}",  # select the correct figure
                "yref": f"y{row}",
                "line": {"width": 0},  # no frames
            }
        )

    # draw a dashed line to show the threshold
    shapes.append(
        {
            "type": "line",
            "x0": time_values.min(),
            "x1": time_values.max(),
            "y0": threshold,
            "y1": threshold,
            "line": dict(color="red", width=2, dash="dash"),
            "layer": "above",
            "xref": f"x{row}",
            "yref": f"y{row}",
        }
    )
    return shapes
