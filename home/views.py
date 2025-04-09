import ast
import json
import math
import os
import random
import string
import urllib
from urllib.parse import urlparse

import numpy as np
import plotly
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
import requests
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page
from influxdb_client import InfluxDBClient
from plotly.subplots import make_subplots
from pyproj import Transformer

from core.tools import (
    SenseBoxTable,
    calculate_centroid,
    calculate_eastern_and_western_longitude,
    fetch_tile,
    get_latest_boxes_with_distance_as_df,
    get_timeframe,
    hexmap_style,
    influx_bucket,
    influx_org,
    influx_token,
    influx_url,
    mapbox_token,
    pd,
    red_shape_creator,
    render_graph,
    run_multithreaded,
    seconds_until_next_hour,
    settings,
)
from home.models import SenseBoxLocation, SensorsInfoTable


# @cache_page(60 * 60)
async def draw_graph(request, sensebox_id: str):
    ###########################################################
    # read influx
    ###########################################################

    query = f"""from(bucket: "{influx_bucket}")
    |> range(start:-3d, stop: now())
    |> filter(fn: (r) => r._measurement == "{sensebox_id}")
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
    """

    client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org, debug=False)
    system_stats = client.query_api().query_data_frame(org="HU", query=query)

    df = system_stats

    df = df.drop(columns=["result", "_measurement", "_start", "_stop", "table"])

    # ToDo: only temp
    if "unit" in df:
        print("drop unit")
        df = df.drop(columns=["unit"])

    column_list = df.columns.to_list()
    column_list.remove("_time")

    # add units to column name -> make them available in the graph later
    columns_with_units = []
    for column in column_list:
        entry = await SensorsInfoTable.objects.filter(name=column).afirst()
        if entry:
            unit = entry.unit
            new_column_name = f"{column} ({unit})"
            columns_with_units.append(new_column_name)
            df.rename(columns={column: new_column_name}, inplace=True)

            # replace all missing values with None, so plotly can detect, that values are missing, and does not draw a connecting line between the last and first value in the gap
            # df[new_column_name] = df[new_column_name].replace(pd.NA, None)
            # df[new_column_name] = df[new_column_name].replace(np.nan, None)
        else:
            print(f"No match for {column}")
            columns_with_units.append(column)

    if len(columns_with_units) != len(column_list):
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>> SOME COLUMNS ARE WITHOUT UNITS")
        print(f"len(columns_with_units): {len(columns_with_units)}")
        print(f"len(column_list): {len(column_list)}")

    # print(df.head())

    # round to 5 min values
    df["_time"] = df["_time"].dt.round(freq="5min").dt.tz_convert(tz="Europe/Berlin")

    # create a new empty df with time values every 5 min (5T)
    full_time_range = pd.date_range(start=df["_time"].min(), end=df["_time"].max(), freq="5T")
    df_full = pd.DataFrame({"_time": full_time_range})

    # merge my df with the one with all time values (df_full)
    df = df_full.merge(df, on="_time", how="left")

    # calc mean of the aggregated values
    df = df.groupby("_time", as_index=False).mean()

    df = df.drop_duplicates()

    ###########################################################
    # draw graph
    ###########################################################

    # print(df.columns.tolist())

    # column_names = {'Temperatur': '°C', 'rel. Luftfeuchte': '%', 'Luftdruck': 'hPa', 'Beleuchtungsstärke': 'lux',
    #                 'UV-Intensität': 'W/m2', 'PM10': 'PM10', 'PM2.5': 'PM2.5',
    #                 'CO₂': 'CO2'}

    rows = len(columns_with_units)
    single_plot_height = 300
    base_height = 250
    text_factor = 10

    fig_height = sum(base_height + len(item) * text_factor for item in columns_with_units)

    fig = make_subplots(
        rows=rows,
        cols=1,
        # vertical_spacing=(1 / (rows - 1)), # Vertical spacing cannot be greater than (1 / (rows - 1)) = 0.062500
        # shared_xaxes=True,
        # subplot_titles=column_list,
    )

    default_colors = plotly.colors.qualitative.Plotly

    row = 0
    all_shapes = []
    for item in columns_with_units:
        row += 1

        x_values = np.array(df["_time"])
        y_values = np.array(df[item])

        is_nan = np.isnan(y_values)

        marker_indices = np.where((~is_nan) & np.roll(is_nan, 1) & np.roll(is_nan, -1))[0]

        marker_x = x_values[marker_indices]
        marker_y = y_values[marker_indices]

        hover_templates = np.array(["%{x}: %{y}"] * len(y_values))
        hover_templates[marker_indices] = ""

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines",
                line=dict(width=5, color=default_colors[row]),
                name=item,
                #hovertemplate=hover_templates,
                #hoverinfo="none",
                #hovertemplate=hover_templates,
                connectgaps=False
            ),
            row=row,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=marker_x,
                y=marker_y,
                mode="markers",
                marker=dict(
                    color='rgba(0,0,0,0)',
                    size=6,
                    line=dict(color=default_colors[row], width=1)
                ),
                hovertemplate="%{x}: %{y}<extra></extra>",
            ),
            row=row,
            col=1,
        )

        fig.update_xaxes(title_text="Zeit (t)", row=row, col=1)
        fig.update_yaxes(title_text=item, row=row, col=1)

        if "PM2.5" in item:
            # Wert pro Kalenderjahr! (Damit PM10 und PM2.5 vergleichbar sind)
            # https://www.umweltbundesamt.de/daten/luft/feinstaub-belastung#bestandteile-des-feinstaubs
            threshold = 25.0
            shapes = await red_shape_creator(threshold, df, item, row)
            all_shapes.extend(shapes)

        if "PM10" in item:
            # Wert pro Kalenderjahr! (Damit PM10 und PM2.5 vergleichbar sind)
            # https://www.umweltbundesamt.de/daten/luft/feinstaub-belastung#bestandteile-des-feinstaubs
            threshold = 40.0
            shapes = await red_shape_creator(threshold, df, item, row)
            all_shapes.extend(shapes)

    # fig.update_yaxes()

    sensebox = await SenseBoxTable.objects.aget(sensebox_id=sensebox_id)

    fig.update_traces(
        # hovertemplate=None#'%{y}'
    )

    fig.update_layout(
        shapes=all_shapes,  # add all red boxes to figure
        hoversubplots="axis",  # no effect!
        hovermode="x",
        # plot_bgcolor='white',
        autosize=True,
        height=fig_height,  # single_plot_height * rows,
        # width=1000,
        title_text=f"{sensebox.name}",
        # title=dict(text=f"{sensebox.name}"),
        template="none",  # https://plotly.com/python/templates/
        # margin=dict(t=45, r=10, l=30, pad=0),
    )

    fig.update_xaxes(
        mirror=True,
        ticks="outside",
        showline=True,
        # showticklabels=True,
        # linecolor='black',
        # gridcolor='lightgrey'
    )

    fig.update_yaxes(
        autorange=True,
        mirror=True,
        ticks="outside",
        showline=True,
        showticklabels=True,
        # linecolor='black',
        # gridcolor='lightgrey'
    )

    fig.update_traces(
        hoverinfo="y+name+x",
        # line={"width": 0.1},
        # marker={"size": 2},
        # mode="lines+markers",
        showlegend=False,
    )

    # graph = plotly.offline.plot(fig, include_plotlyjs=False, output_type='div')
    graph = await render_graph(fig)

    return HttpResponse(graph)


# @cache_page(60 * 60)
async def single(request):
    # start_timer = time.time()

    # ToDo: https://lab.taschenfussel.de/s/erfrischungskarte/14Uhr/ and more ...

    ########################
    # hexmap part
    ########################

    # collect all sensors (huge table!)
    query = f"""from(bucket: "{influx_bucket}")
        |> range(start: -12h, stop: now())
        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
    """

    client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org, debug=False)
    system_stats = client.query_api().query_data_frame(org="HU", query=query)

    df = pd.concat(system_stats, ignore_index=True, join="outer", axis=0)
    df = df.drop(
        columns=[
            "_start",
            "_stop",
            "table",
            "result",
            "_time",
            #"_value",
            #"_field",
            "_measurement",
        ]
    )
    item_list = df.columns.to_list()

    # Sensor
    context = {
        "name": "ressource_path",
        "item_list": item_list,
        "selected": "Temperatur",
        "description": "Sensor",
    }
    graph = render_to_string(template_name="home/fragments/select.html", context=context, request=request)

    # Time
    context = {
        "name": "start_time",
        "item_list": [i for i in range(1, 169)],
        "selected": 48,
        "description": "Zeitfenster",
        "additional_info": "Anzeigen der letzten ... Stunden",
    }
    graph += render_to_string(template_name="home/fragments/select.html", context=context, request=request)

    # Colors
    colors_list = [
        attr for attr in dir(px.colors.sequential) if not attr.startswith("_") and not attr.startswith("swatches")
    ]
    context = {
        "name": "colorscale",
        "item_list": colors_list,
        "selected": "Turbo",
        "description": "Farbschema",
        "additional_info": '<a href="https://plotly.com/python/builtin-colorscales" target="_blank">See all supported <i>sequential colors</i></a>',
    }
    graph += render_to_string(template_name="home/fragments/select.html", context=context, request=request)

    # Map style
    context = {
        "name": "map_style",
        "item_list": hexmap_style,
        "selected": "light",
        "description": "Kartentyp",
        "additional_info": "",
    }
    graph += render_to_string(template_name="home/fragments/select.html", context=context, request=request)

    # Hexagon size
    context = {
        "name": "resolution",
        "item_list": [i for i in range(1, 61)],
        "selected": 15,
        "description": "Auflösung",
        "additional_info": "Höhere Werte = höhere Auflösung und kleinere Hexagone, <br>maximale horizontale Distanz zwischen zwei SenseBoxen geteilt durch ausgewählten Wert,<br>Standardbreite: 60 km / 15 ≈ 4 km",
    }

    # set default
    params = {
        "ressource_path": "Temperatur",
        "start_time": 48,
        "colorscale": "Turbo",
        "map_style": "light",
        "resolution": 15,
    }
    await sync_to_async(set_session)(request, params)

    ########################
    # end hexmap part
    ########################

    graph += render_to_string(template_name="home/fragments/select.html", context=context, request=request)

    context["graph"] = graph

    # set default
    # await sync_to_async(set_session)(request, {'ressource_path': 'Temperatur', 'start_time': '48', 'colorscale': 'Turbo'})

    return await sync_to_async(render)(request, "home/customizer.html", context)


def set_session(request, value):
    request.session["last_params"] = value


def get_session(request):
    if "last_params" in request.session:
        return request.session["last_params"]
    else:
        return {}


async def url_string_generator(request):

    last_params = await sync_to_async(get_session)(request)
    new_params = request.GET.dict()
    params = last_params | new_params
    await sync_to_async(set_session)(request, params)
    encoded_params = urllib.parse.urlencode(params)
    url_string = "/s/hexmap" + "?" + encoded_params
    # link_to_url = f"<a href='{url_string}' target='_blank'>{url_string}</a>"

    link_button = f"""
                    <a id="play-button" href="{url_string}" class="btn btn-primary btn-lg" target="_blank">
                        <i class="fas fa-play fa-2xl"></i>
                    </a>
    """

    return HttpResponse(link_button)


# @cache_page(60 * 60)


def create_hexmap(df, ressource, resolution, label, colorscale, zoom_level, center):
    return ff.create_hexbin_mapbox(
        data_frame=df,
        lat="latitude",
        lon="longitude",
        color=ressource,
        nx_hexagon=resolution,  # Number of hexagons (horizontally) to be created
        opacity=0.7,
        labels=label,
        animation_frame="_time",
        min_count=1,
        agg_func=np.mean,
        show_original_data=True,
        original_data_marker=dict(size=4, opacity=1.0, color="deeppink"),
        color_continuous_scale=f"{colorscale}",
        zoom=zoom_level,  # Between 0 and 20. Sets map zoom level.
        center=center,  # Dict keys are 'lat' and 'lon' Sets the center point of the map.
    )


async def hexmap(request):

    cache_time = seconds_until_next_hour()

    ressource = request.GET.get("ressource_path", "Temperatur")
    colorscale = request.GET.get("colorscale", "Turbo")
    start_time = request.GET.get("start_time", 48)
    resolution = request.GET.get("resolution", 15)  # Number of hexagons (horizontally) to be created
    zoom_level = request.GET.get("zoom_level", 10)
    map_style = request.GET.get("map_style", "light")

    cache_key = f"hexmap_{ressource}_{colorscale}_{start_time}_{resolution}_{zoom_level}_{map_style}"

    #print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> cache_key: {cache_key}")

    graph = None

    if not settings.DEBUG:
        graph = cache.get(cache_key)

    if graph is not None:
        print("+++++++++ found graph in cache")
    else:
        print("--------- found no graph in cache generate new")

        resolution = int(resolution)

        query = f"""from(bucket: "{influx_bucket}")
            |> range(start: -{start_time}h, stop: now())
            |> filter(fn: (r) => r["_field"] == "{ressource}")
            |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        """

        client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org, debug=False)
        df = client.query_api().query_data_frame(org="HU", query=query)

        # ToDo: sytem_stats empty -> no data fetched (show a message)

        #df = pd.concat(system_stats, ignore_index=True, join="outer", axis=0)  # .groupby('_time', axis=0)

        df = df.drop(columns=["_start", "_stop", "table", "result"])

        ressource_list = df.columns.to_list()
        # print(f">>>>>>>>>>>>>>>>>>>>>>>>>> {ressource_list}")

        if ressource in ressource_list:
            pass
        else:
            df = df.drop(columns=["_time", "_measurement"])
            ressource_list = df.columns.to_list()

            return HttpResponse(
                f"""<div>
            List of valid sensors: <br>{ressource_list}
            <br>
            <a href="https://plotly.com/python/builtin-colorscales" target="_blank">Click here to see all supported <i>sequential colors</i></a>
            <br>
            create a URL in style of: /s/draw_hexmap/rel. Luftfeuchte?colorscale=Plotly3
            
            </div>"""
            )
            # raise Exception(f">>>>>>>>>>> No results for {ressource}")

        if map_style not in hexmap_style:
            return HttpResponse(
                f"""<div>
            List of valid map styles: <br>{hexmap_style}
            </div>"""
            )

        id_and_location_dict = {}

        async for entry in SenseBoxTable.objects.all():
            id_and_location_dict[entry.sensebox_id] = [
                float(entry.location_latitude),
                float(entry.location_longitude),
            ]

        df["latitude"] = df["_measurement"].map(lambda x: id_and_location_dict.get(x, [None, None])[0]) # MUCH (~100x) faster than using apply()
        df["longitude"] = df["_measurement"].map(lambda x: id_and_location_dict.get(x, [None, None])[1])

        df.dropna(inplace=True, subset=["latitude", "longitude"])

        df = df[["_time", "latitude", "longitude", ressource]] # remove all unwanted columns to save (a lot) space!

        df["_time"] = df["_time"].dt.round(freq="60min").dt.tz_convert(tz="Europe/Berlin")
        df = df.groupby(["_time", "latitude", "longitude"], as_index=False).mean() # Mean of "all" columns without coordinates

        # convert to more beautifully human-readable STRING
        df["_time"] = df["_time"].dt.strftime("%d.%m. %H:%M")

        # print(f"value: {df['_time'].iloc[0]}, type: {type(df['_time'].iloc[0])}")

        px.set_mapbox_access_token(mapbox_token)

        df.dropna(inplace=True, subset=[ressource])

        # Remove values, that are way off the limit and are probably wrong!
        # median = df[ressource].median()  # mean()
        # df = df[
        #     (df[ressource] >= 0.1 * median) & (df[ressource] <= 10 * median)
        # ]  # mehr als 1000 % vom Median (oder Mittelwert)

        # The temperatur sensor from this box causes problems:
        # https://opensensemap.org/explore/60c14256b2a183001cd39959
        # 1%- und 99%-Quantil
        q_low, q_high = df[ressource].quantile([0.01, 0.99])
        df = df[(df[ressource] >= q_low) & (df[ressource] <= q_high)]

        if ressource == "Temperatur":
            label = {"color": "°C"}
        else:
            label = {"color": ressource}

        """
        A function to plot several hexmaps onto the same map
        
        We need several things to do that:
            - we need to estimate how long the distance is "longitude" -> convert form length to geo coordinate
            - then, we want to adjust, how big a single hexagon needs to be, to get a good representation for the data
            - make this changeable from user perspective
        """

        location = await SenseBoxLocation.objects.aget(name="Berlin")

        center = {
            "lat": float(location.location_latitude),
            "lon": float(location.location_longitude),
        }

        eastern_longitude, western_longitude = await calculate_eastern_and_western_longitude(
            location.location_longitude,
            location.maxDistance / 1000,  # convert m to km
            location.location_latitude,
        )

        # add eastern and western bound -> important for the hexagon size and resolution!
        df.loc[len(df)] = {"longitude": eastern_longitude}
        df.loc[len(df)] = {"longitude": western_longitude}

        """
        End Section
        """

        fig = create_hexmap(df, ressource, resolution, label, colorscale, zoom_level, center)

        #fig.update_traces(hovertemplate=None)

        # fig.data[0].hovertemplate = (
        #     "Wert: %{z}<br>"  # Aggregierter Wert der Hexbin-Zelle
        #     "Anzahl Punkte: %{customdata[0]}<br>"  # Anzahl der Datenpunkte
        #     "Koordinaten: (%{lat}, %{lon})<extra></extra>"  # Hexbin-Koordinaten
        # )

        """
        Some day, it may be possible to get a good template with this code. But not today!
        """
        # entry = await SensorsInfoTable.objects.filter(name=ressource).afirst()
        #
        # #for data in fig.data:
        # fig.data[0].hovertemplate = 'PM10: %{z:}<extra></extra>'
        # print("Z-Werte im Plotly-Objekt:", fig.data[0].z)
        #
        # print(len(fig.data))
        #     #data.hoverinfo = "z"
        #
        # for data in fig.data:
        #     print(data)
        #
        # print("###############################################################################")
        #
        # for f in fig.frames:
        #     print(f)
        #     f.Frame.hovertemplate = '%{z}<extra>' + entry.unit + '</extra>'
        #
        # fig.update_layout(
        #     #hovermode="x unified",
        #     autosize=True,
        #     mapbox_style=map_style,
        #     margin=dict(b=0, t=30, l=0, r=0, pad=0),
        # )

        try:
            # fig.update_yaxes(automargin=True)
            fig.layout.sliders[0].pad.t = 5
            fig.layout.sliders[0].pad.l = 0
            fig.layout.updatemenus[0].pad.t = 5
            fig.layout.updatemenus[0].pad.l = 0
        except IndexError:
            return HttpResponse(
                f"""<div>
                        <h1>{ressource} hat zu wenig Daten in dem gewählten Zeitraum gemeldet</h1>
                        
                        <p>Die Menge der gemeldeten Daten reicht nicht aus eine Grafik zu zeichnen.</p>
                        
                        <p>Not enough values for {ressource} in the selected timeframe.</p>
                    </div>"""
            )

        # fig.update_geos(fitbounds="locations")

        graph = await render_graph(fig)

        cache.set(cache_key, graph, timeout=int(cache_time))

    if request.path.startswith("/s/"):
        return render(request, "home/single_page.html", {"graph": graph})

        # return await sync_to_async(render)(request, "home/single_page.html", {"graph": graph})
    else:
        return HttpResponse(graph)


@cache_page(60 * 60 * 24 * 30)
async def erfrischungskarte(request, this_time="14Uhr"):
    color_sets = {
        "jennifers_farben": [
            "#E6CCE6",
            "#AD99EC",
            "#7366F3",
            "#3A33F9",
            "#0000FF",  # x-Achse, spaltenweise
            "#EC99AD",
            "#CD99CD",
            "#B080D0",
            "#9366D3",
            "#764DD6",  #
            "#F36673",
            "#D080B0",
            "#B366B3",
            "#974DB6",
            "#7A33B9",  #
            "#F9333A",
            "#D36693",
            "#B64D97",
            "#9A339A",
            "#7D1A9D",  #
            "#FF0000",
            "#D64D76",
            "#B9337A",
            "#9D1A7D",
            "#800080",  # Mischung bis zum kräftigsten Wert
        ],
    }

    """
    Function to set default variables
    """

    def conf_defaults() -> dict:
        # Define some variables for later use
        default_conf = {
            "plot_title": "Bivariate choropleth map using Ploty",  # Title text
            "plot_title_size": 9,  # Font size of the title
            "width": 1000,  # Width of the final map container
            "ratio": 0.8,  # Ratio of height to width
            "center_lat": 0,  # Latitude of the center of the map
            "center_lon": 0,  # Longitude of the center of the map
            "map_zoom": 3,  # Zoom factor of the map
            "map_style": "open-street-map",
            "hover_x_label": "Label x variable",  # Label to appear on hover
            "hover_y_label": "Label y variable",  # Label to appear on hover
            "borders_width": 0.1,  # Width of the geographic entity borders
            "borders_color": "#f8f8f8",  # Color of the geographic entity borders
            # Define settings for the legend
            "top": 1,  # Vertical position of the top right corner (0: bottom, 1: top)
            "right": 1,  # Horizontal position of the top right corner (0: left, 1: right)
            "box_w": 0.03,  # Width of each rectangle
            "box_h": 0.03,  # Height of each rectangle
            "line_color": "#f8f8f8",  # '#f8f8f8',  # Color of the rectagles' borders
            "line_width": 0,  # Width of the rectagles' borders
            "legend_x_label": "Higher x value",  # x variable label for the legend
            "legend_y_label": "Higher y value",  # y variable label for the legend
            "legend_font_size": 11,  # Legend font size
            "legend_font_color": "#333",  # Legend font color
            "time": this_time,
        }

        # Calculate height
        default_conf["height"] = default_conf["width"] * default_conf["ratio"]

        return default_conf

    """
    Function to recalculate values in case width is changed
    """

    def recalc_vars(new_width, variables, default_conf=None):
        if default_conf is None:
            default_conf = conf_defaults()
        # Calculate the factor of the changed width

        factor = new_width / 1000

        # print(f'width: {new_width}')

        # for var in variables:
        #    print(conf[var])

        # Apply factor to all variables that have been passed to th function
        for var in variables:
            if var == "map_zoom":
                # Calculate the zoom factor
                # Mapbox zoom is based on a log scale. map_zoom needs to be set to value ideal for our map at 1000px.
                # So factor = 2 ^ (zoom - map_zoom) and zoom = log(factor) / log(2) + map_zoom
                default_conf[var] = math.log(factor) / math.log(2) + default_conf[var]
            else:
                default_conf[var] = default_conf[var] * factor

        # print(f'width: {new_width}')

        # for var in variables:
        #    print(conf[var])

        return default_conf

    """
    Transform coordinates (alt)
    """

    """
    Function to load GeoJSON file with geographical data of the entities
    """

    def load_geojson(geojson_url, local_file: str, data_dir: str = "refreshing_data"):
        # Make sure data_dir is a string
        data_dir = str(data_dir)

        # Set name for the file to be saved
        if not local_file:
            # Use original file name if none is specified
            url_parsed = urlparse(geojson_url)
            local_file = os.path.basename(url_parsed.path)
            print("Set name for local file.")
        else:
            pass
            # print(f'Local file name is {local_file}')

        geojson_file = data_dir + "/" + str(local_file)

        # Create folder for data if it does not exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            print("Created data folder!")
        else:
            pass
            # print('Data dir exists.')

        # Download GeoJSON in case it doesn't exist
        if not os.path.exists(geojson_file):
            print("Download file ...")

            # Make http request for remote file data
            geojson_request = requests.get(geojson_url)

            # Save file to local copy
            with open(geojson_file, "wb") as file:
                file.write(geojson_request.content)

            print("Downloaded!")
        else:
            pass
            # print('Local file exists.')

        # print('try to load geojson')

        # Load GeoJSON file
        geojson = json.load(open(geojson_file, "r"))

        # print('geojson loaded')

        transformer = Transformer.from_crs("epsg:32633", "epsg:4326", always_xy=True)

        def transform_coordinates(coordinates):

            if isinstance(coordinates[0], list):  # Verschachtelte Koordinaten (z.B. bei Polygonen)
                return [transform_coordinates(coord) for coord in coordinates]
            else:
                # Einzelne Koordinaten (x, y) umwandeln
                lon, lat = transformer.transform(coordinates[0], coordinates[1])
                return [lon, lat]

        # Iteriere über alle Features und transformiere die Koordinaten
        for feature in geojson["features"]:
            geom_type = feature["geometry"]["type"]

            if geom_type in [
                "Polygon",
                "MultiPolygon",
                "LineString",
                "MultiLineString",
            ]:
                feature["geometry"]["coordinates"] = transform_coordinates(feature["geometry"]["coordinates"])

        # print('transformed geojson')

        # Return GeoJSON object
        return geojson

    """
    Function that assigns a value (x) to one of three bins (0, 1, 2).
    The break points for the bins can be defined by break_a and break_b.
    """

    """
    Function that adds a column 'biv_bins' to the dataframe containing the
    position in the 25-color matrix for the bivariate colors

    Arguments:
        df: Dataframe
        x: Name of the column containing values of the first variable
        y: Name of the column containing values of the second variable

    """

    def prepare_df(df, x="wind", y="temp"):
        # Check if arguments match all requirements
        if df[x].shape[0] != df[y].shape[0]:
            raise ValueError("ERROR: The list of x and y coordinates must have the same length.")

        new_df = df
        new_df.dropna(inplace=True)
        new_df[x] = new_df[x].astype("int") - 1
        new_df[y] = new_df[y].astype("int") - 1

        # print('before replacement')
        # print(new_df.head())

        # Replace values in temp to match legend
        # new_df[y] = new_df[y].replace([0, 1, 3, 4], [4, 3, 1, 0])
        # new_df[x] = new_df[x].replace({0: 4, 1: 3})

        # print('after replacement')
        # print(new_df.head())

        # Calculate the position of each x/y value pair in the 25-color matrix of bivariate colors
        new_df["biv_bins"] = [value_x + 5 * value_y for value_x, value_y in zip(new_df[x], new_df[y])]

        return new_df

    """
    Function to create a color square containig the 25 colors to be used as a legend
    """

    def create_legend(fig, colors, default_conf=None):
        if default_conf is None:
            default_conf = conf_defaults()

        # print(f'orginal order: {colors[:]}')

        if len(colors) < 25:
            print(f"Len of colors not right (should be 25): {len(colors)}")

        # Reverse the order of colors
        legend_colors = colors[:]
        legend_colors.reverse()

        # print(f'reversed order: {legend_colors}')

        # Calculate coordinates for all 25 rectangles
        coord = []

        # Adapt height to ratio to get squares
        width = default_conf["box_w"]
        height = default_conf["box_h"]  # /default_conf['ratio']

        # Start looping through rows and columns to calculate corners the squares
        for row in range(1, 6):
            for col in range(1, 6):
                coord.append(
                    {
                        "x0": round(default_conf["right"] - (col - 1) * width, 2),
                        "y0": round(default_conf["top"] - (row - 1) * height, 2),
                        "x1": round(default_conf["right"] - col * width, 2),
                        "y1": round(default_conf["top"] - row * height, 2),
                    }
                )

        # print(coord)

        # Create shapes (rectangles)
        for i, value in enumerate(coord):
            # Add rectangle
            fig.add_shape(
                go.layout.Shape(
                    type="rect",
                    fillcolor=legend_colors[i],
                    # label_text=i, # name the colors
                    line=dict(
                        color=default_conf["line_color"],
                        width=default_conf["line_width"],
                    ),
                    xref="paper",
                    yref="paper",
                    xanchor="right",
                    yanchor="top",
                    x0=coord[i]["x0"],
                    y0=coord[i]["y0"],
                    x1=coord[i]["x1"],
                    y1=coord[i]["y1"],
                )
            )

            # Add text for first variable
            fig.add_annotation(
                xref="paper",
                yref="paper",
                xanchor="left",
                yanchor="top",
                x=coord[24]["x1"],
                y=coord[24]["y1"],
                showarrow=False,
                text=default_conf["legend_x_label"] + " ->",
                font=dict(
                    color=default_conf["legend_font_color"],
                    size=default_conf["legend_font_size"],
                ),
                borderpad=0,
            )

            # Add text for second variable
            fig.add_annotation(
                xref="paper",
                yref="paper",
                xanchor="right",
                yanchor="bottom",
                x=coord[24]["x1"],
                y=coord[24]["y1"],
                showarrow=False,
                text=default_conf["legend_y_label"] + " ->",
                font=dict(
                    color=default_conf["legend_font_color"],
                    size=default_conf["legend_font_size"],
                ),
                textangle=270,
                borderpad=0,
            )

        return fig

    """
    Function to create the map

    Arguments:
        df: The dataframe that contains all the necessary columns
        colors: List of 25 blended colors
        x: Name of the column that contains values of first variable (defaults to 'x')
        y: Name of the column that contains values of second variable (defaults to 'y')
        ids: Name of the column that contains ids that connect the data to the GeoJSON (defaults to 'id')
        name: Name of the column conatining the geographic entity to be displayed as a description (defaults to 'name')
    """

    def create_bivariate_map(
        df,
        colors,
        geojson,
        x="wind",
        y="temp",
        ids="id",
        name="name",
        default_conf=None,
    ):
        if default_conf is None:
            default_conf = conf_defaults()
        if len(colors) != 25:
            raise ValueError("ERROR: The list of bivariate colors must have a length eaqual to 25.")

        # Recalculate values if width differs from default
        if not default_conf["width"] == 1000:
            default_conf = recalc_vars(
                default_conf["width"], ["map_zoom"], default_conf
            )  # 'height', 'plot_title_size', 'legend_font_size',

        # Prepare the dataframe with the necessary information for our bivariate map
        df_plot = prepare_df(df, x, y)

        # print(df_plot.head())
        # print(df_plot)

        # Create the figure
        fig = go.Figure(
            go.Choroplethmap(
                geojson=geojson,
                locations=df_plot[ids],
                z=df_plot["biv_bins"],
                marker_line_width=0.5,
                colorscale=[[i / 24, colors[i]] for i in range(25)],
                # colorscale='Hot',
                customdata=df_plot[["id", "wind", "temp", "biv_bins"]],  # Add data to be used in hovertemplate
                hovertemplate="<br>".join(
                    [  # Data to be displayed on hover
                        "<b>%{customdata[0]}</b>",
                        default_conf["hover_x_label"] + ": %{customdata[1]}",
                        default_conf["hover_y_label"] + ": %{customdata[2]}",
                        "MV: %{customdata[3]}",
                        "<extra></extra>",  # Remove secondary information
                    ]
                ),
            )
        )

        # Add some more details
        fig.update_layout(
            title=dict(
                text=default_conf["plot_title"],
                font=dict(
                    size=default_conf["plot_title_size"],
                ),
            ),
            map_style="white-bg",
            # width=default_conf['width'],
            # height=default_conf['height'],
            autosize=True,
            map=dict(
                center=dict(lat=default_conf["center_lat"], lon=default_conf["center_lon"]),  # Set map center
                zoom=default_conf["map_zoom"],  # Set zoom
            ),
        )

        fig.update_traces(
            marker_line_width=default_conf["borders_width"],  # Width of the geographic entity borders
            marker_line_color=default_conf["borders_color"],  # Color of the geographic entity borders
            showscale=False,  # Hide the colorscale
        )

        # Add the legend
        fig = create_legend(fig, colors, default_conf)

        return fig

    def custom_conf(this_time):
        # Load conf defaults
        custom_conf = conf_defaults()

        # Override some variables
        custom_conf["plot_title"] = "Berliner Erfrischungskarte"
        custom_conf["width"] = 1000  # Width of the final map container
        custom_conf["ratio"] = 0.8  # Ratio of height to width
        custom_conf["height"] = custom_conf["width"] * custom_conf["ratio"]  # Width of the final map container
        custom_conf["center_lat"] = 52.516221  # Latitude of the center of the map
        custom_conf["center_lon"] = 13.3992  # Longitude of the center of the map
        custom_conf["map_zoom"] = 10  # Zoom factor of the map
        custom_conf["map_style"] = ("open-street-map",)  # open-street-map
        custom_conf["hover_x_label"] = "windig"  # Label to appear on hover
        custom_conf["hover_y_label"] = "warm"  # Label to appear on hover

        # Define settings for the legend
        custom_conf["line_width"] = 0.5  # Width of the rectagles' borders
        custom_conf["legend_x_label"] = "windiger"  # x variable label for the legend
        custom_conf["legend_y_label"] = "wärmer"  # y variable label for the legend

        custom_conf["time"] = this_time

        return custom_conf

    def load_data(default_conf):
        # Define URL of the GeoJSON file
        wind_url = "https://raw.github.com/technologiestiftung/erfrischungskarte-daten/main/Wind_Temperature/data/clean/t_Wind_9bis21.geojson"
        # Load GeoJSON file
        wind = load_geojson(wind_url, local_file="t_Wind_9bis21.geojson")

        # print('loaded wind')

        temp_url = "https://raw.github.com/technologiestiftung/erfrischungskarte-daten/main/Wind_Temperature/data/clean/t_Temperatur_9bis21.geojson"
        # Load GeoJSON file
        temperature = load_geojson(temp_url, local_file="t_Temperatur_9bis21.geojson")

        # print('loaded temp')

        df_list = []
        for idx, feature in enumerate(wind["features"]):
            # feature['id'] = f"{'idx': idx}, {'type': 'id'}"
            feature["id"] = idx
            df_list.append({"id": idx, "wind": feature["properties"][default_conf["time"]]})
        wind_df = pd.DataFrame(df_list)

        df_list = []
        for idx, feature in enumerate(temperature["features"]):
            # feature['id'] = f"{'idx': idx}, {'type': 'id'}"
            feature["id"] = idx
            df_list.append({"id": idx, "temp": feature["properties"][default_conf["time"]]})
            # if feature["properties"]["14Uhr"] == 1.0:
            #    print(idx)
            # print(f'{idx}: {feature["properties"]["14Uhr"]}')
        temp_df = pd.DataFrame(df_list)

        bivariate_df = pd.merge(wind_df, temp_df, on="id")
        # bivariate_df.head()

        return wind, temperature, bivariate_df

    # Create our bivariate map
    custom_conf = custom_conf(this_time)
    wind, temperature, bivariate_df = load_data(default_conf=custom_conf)
    fig = create_bivariate_map(bivariate_df, color_sets["jennifers_farben"], wind, default_conf=custom_conf)

    fig.update_layout(
        margin=dict(b=0, t=30, l=0, r=0),
    )

    # graph = plotly.offline.plot(fig, include_plotlyjs=False, output_type='div',
    #                             image_width='100%',
    #                             image_height='100%',
    #                             auto_open=False,
    #                             config={
    #                                 'displayModeBar': True,
    #                                 'displaylogo': False,
    #                                 'responsive': True,
    #                                 'modeBarButtonsToRemove': [
    #                                     'zoom',
    #                                     'pan',
    #                                     'toImage',
    #                                     'resetViewMapbox',
    #                                     'select',
    #                                     'toggleHover',
    #                                     'lasso2d',
    #                                     'pan2d',
    #                                     'select2d',
    #                                 ],
    #                             })
    graph = await render_graph(fig)

    if request.path.startswith("/s/"):
        return await sync_to_async(render)(request, "home/single_page.html", {"graph": graph})
    else:
        return HttpResponse(graph)


# no cache_page here, please! It will disturb the generation of new cards.
async def show_by_tag(request, region: str = "Berlin", box: str = "all", cache_time: int = 60) -> HttpResponse:
    """
    ToDo: Attention, this is old and not true any more!
    1. get_latest_boxes_with_distance_as_df() -> seems complex, but this is much faster to do so!
        (much faster than https://docs.opensensemap.org/#api-Measurements-getDataByGroupTag)
    2. get_boxes_with_tag(tagname) -> create a new df from filtered db
    3. run_multithreaded(df) -> get a list of df, concatenate them (they have the id in attr)
    """

    template_to_use = request.GET.get("template", "dashboard_single_grouptag")
    permanent_name = request.GET.get("permanent_name", None)
    old_unique_name = request.GET.get("unique_name", "empty") # legacy
    tag = request.GET.get("tag", "Humboldt Explorers")

    df = await get_latest_boxes_with_distance_as_df(region, cache_time=cache_time)

    # remove all boxes with empty grouptags
    df = df.dropna(subset=["grouptag"])
    found_grouptags = df["grouptag"]

    # filter rows for "tag", keep only those
    df = df[df["grouptag"].apply(lambda x: tag in x)]

    tag_summary = []
    for tag_list in found_grouptags:
        for this_tag in tag_list:
            if this_tag != "" and this_tag != " ":
                tag_summary.append(this_tag)
    # remove double entries by convert it to dict and then to list again
    found_grouptags = list(dict.fromkeys(tag_summary))
    # then show this in the dropdown menu

    # when there is nothing to show, return an empty list
    if df.empty:
        print(">>>>>>>>>>>>>> tag is empty")
        return render(
            request,
            template_name=f"home/sub_templates/{template_to_use}.html",
            context={
                "box": box,
                "tag": tag,
                "no_results_for_tag": tag,
                "found_grouptags": found_grouptags,
            },
        )

    # I've got get_latest_boxes_with_distance_as_df() and found all boxes with tags
    # Now I want to get all sensor data.
    # ToDo: What timeframe is actually needed. Are 5 h enough?
    timeframe = await get_timeframe(1.0 + 1 / 24)  # timeframe 1 day + 1 hour!

    # Use caching here to store data for a short time
    cache_key = f"{tag}-{timeframe}"
    results = cache.get(cache_key)
    if results is None:
        print("No multiprocessing results in cache")
        # this function calls all boxes with the selected tag!
        results = await run_multithreaded(df, timeframe)
        cache.set(cache_key, results, timeout=cache_time)
    else:
        print("Got multiprocessing results from cache")

    df.drop(
        columns=[
            "createdAt",
            "updatedAt",
            "exposure",
            "image",
            "weblink",
            "description",
            "model",
        ],
        inplace=True,
    )

    combined_list = []
    # get one box after another as pd.Series
    for b_index, s_box in df.iterrows():
        # create a dict to use it later to match sensor title with unit to display
        unit_dict = {}
        for s in s_box["sensors"]:
            unit_dict[s["title"]] = {"unit": s["unit"], "sensorId": s["_id"]}

        # a combined dict that will act as a row later in the df
        for r in results:  # get one sensor after another as df
            if s_box["_id"] == r.attrs["box_id"]:  # check if this the box matches the one from the sensor df

                for s_index, s_sensor in r.iterrows():  # sensors now as Series

                    # from here on I read the sensor values
                    for item in s_sensor.items():  # iterate over series items

                        combined_dict = {
                            "createdAt": s_sensor.name,  # set datetime for all sensor reading (they come all at the same time)
                            "boxId": s_box["_id"],
                            "grouptag": s_box["grouptag"],
                            "name": s_box["name"],
                            "lat": s_box["currentLocation"]["coordinates"][1],
                            "lon": s_box["currentLocation"]["coordinates"][0],
                            "title": item[0],
                            "value": item[1],
                            "unit": unit_dict[item[0]]["unit"] if item[0] in unit_dict else "",
                            "sensorId": unit_dict[item[0]]["sensorId"] if item[0] in unit_dict else "",
                        }
                        combined_list.append(combined_dict)  # append this new created dict (aka row) to the list

    # create a df from that
    df = pd.DataFrame(combined_list)

    # convert createdAt to datetime
    df["createdAt"] = pd.to_datetime(df["createdAt"], format="%Y-%m-%dT%H:%M:%S.%fZ", utc=True)
    df["createdAt"] = df["createdAt"].dt.tz_convert(tz="Europe/Berlin")

    # print(df['createdAt'].max())

    # value = measured data
    df["value"] = pd.to_numeric(df["value"])

    # when set the index from a time series, the data becomes order able by time
    # df = df.set_index("createdAt")

    # remove all double entries for value 'name'
    name_list = df["name"].unique()

    # create a list from those names
    df_name_list = []
    for name in name_list:
        df_name_list.append(df[df["name"] == name])

    # this was only necessary for development
    df_test = df

    # create a new column with average values from measured data, using median!
    df_test["value_avg"] = df_test.groupby([df_test.index, "title"])["value"].transform("median").round(2)

    """ get latest values from this df for a certain sensebox. """

    # show one or all boxes
    if box != "all":
        single_box_df = df_test[df_test["name"] == box]

        # print(single_box_df.head())
        # print(single_box_df.columns)
        # print(box)
        # print(single_box_df.shape)
        # print(single_box_df.iloc[0])

        # print(f"lat: {df_test['lat'].iloc[0]}, lon: {df_test['lon'].iloc[0]}")
        lat = str(round(single_box_df["lat"].iloc[0], 6)).replace(",", ".")
        lon = str(round(single_box_df["lon"].iloc[0], 6)).replace(",", ".")
    else:
        single_box_df = df_test

        # get all coordinates, to calculate the "centroid", so the center of all values. This is the pin on the map, we will see later.
        coordinates = []
        for i, row in df_test.iterrows():
            coordinates.append({"lat": row["lat"], "lon": row["lon"]})

        lat, lon = calculate_centroid(coordinates=coordinates)
    # print(f"lat: {lat}, lon: {lon}")

    # get a list of all unique sensors, tile = sensor name
    sb_sensor_names_list = single_box_df["title"].unique()

    # show only the absolut last measured sensor value

    # this handy list with the cool name "list_of_dicts_with_rows_and_graphs" is used in the template to render the very last measured values with a nice little graph
    list_of_dicts_with_rows_and_graphs = []
    for sensor in sb_sensor_names_list:
        sensor_dict_row_and_graph = {}

        single_sensor_df = single_box_df[single_box_df["title"] == sensor]
        sensor_dict_row_and_graph["row"] = single_sensor_df[
            single_sensor_df.index == single_sensor_df.index.max()
        ].to_dict("list")
        # if template_to_use == 'dashboard_single_grouptag':
        sensor_dict_row_and_graph["graph"] = await draw_single_sensor_df_graph(single_sensor_df)
        list_of_dicts_with_rows_and_graphs.append(sensor_dict_row_and_graph)

    # reset index, so the function drop_duplicates can work
    # df_test = df_test.reset_index()

    # Here we get all strings from the colum 'grouptag'
    # All rows contain the same combination of grouptags, so it is enough to only get the very first value in the first row
    grouptags = df_test["grouptag"].iloc[0]
    # create a real python list from all strings, if not already a real list
    if not isinstance(grouptags, list):
        grouptags = ast.literal_eval(grouptags)
        # print(f"changed grouptag type from str to list: {grouptags}")

    # We need to remove whitespace from the tagname, because we want to create an url from that :)
    tag = tag.replace(" ", "+")

    # here we create a random string. We need this in the template. So we can draw more than one additional map on the screen.
    # Here we should be able to draw as many as we want.
    lower_chars = string.ascii_lowercase
    unique_name = "".join(random.choice(lower_chars) for _ in range(6))

    if not permanent_name and template_to_use != "dashboard_single_grouptag":
        permanent_name = "".join(random.choice(lower_chars) for _ in range(6))

    # print("Permanent name: ", permanent_name)
    # print(f"template to use 2: {template_to_use}")

    # print(f">>> send box: {box}")
    # print(f">>> send tag: {tag}")

    context = {
        "permanent_name": permanent_name,
        "unique_name": unique_name,
        "old_unique_name": old_unique_name,
        #'graph': graph,
        "name_list": name_list,
        "list_of_dicts_with_rows_and_graphs": list_of_dicts_with_rows_and_graphs,
        "grouptag": grouptags,
        "box": box,  # box name
        "lat": lat,
        "lon": lon,
        "tag": tag,
        "found_grouptags": found_grouptags,
    }

    if request.path.startswith("/s/"):
        graph = render_to_string(
            template_name=f"home/sub_templates/{template_to_use}.html",
            context=context,
            request=request,
        )

        return await sync_to_async(render)(request, "home/single_page.html", context={"graph": graph})
    else:
        return render(
            request,
            template_name=f"home/sub_templates/{template_to_use}.html",
            context=context,
        )


async def draw_single_sensor_df_graph(df):
    """helper function to draw nice graphs for the dashboard"""

    # print(df.head())
    # print(df.info())
    # print(df.columns)

    title = df["title"].iloc[0]

    fig = px.line(
        df,
        x=df["createdAt"],
        y="value",
        labels={
            "value": f"{title} ({df['unit'].iloc[0]})",
            "createdAt": "Zeit (t)",
        },
        color="name",
    )

    # print(f">>>>>>>>>>>>>>>>>>>>>> {df.columns}")
    # Index(['boxId', 'grouptag', 'name', 'lat', 'lon', 'title', 'value', 'unit', 'sensorId', 'value_avg'], dtype='object')

    all_shapes = []

    if title == "PM10":
        threshold = 40.0
        shapes = await red_shape_creator(threshold, df, "title", 1)
        all_shapes.extend(shapes)
    if title == "PM2.5":
        threshold = 25.0
        shapes = await red_shape_creator(threshold, df, "title", 1)
        all_shapes.extend(shapes)

    fig.update_layout(
        shapes=all_shapes,
        plot_bgcolor="white",
        height=300,
        margin=dict(b=0, t=10, l=0, r=10, pad=0),
        showlegend=False,
        # legend=dict(
        #     orientation="h",
        #     entrywidth=70,
        #     yanchor="bottom",
        #     y=1.02,
        #     xanchor="right",
        #     x=1
        # )
    )

    fig.update_traces(
        hovertemplate="%{y}" + f' {df["unit"].iloc[0]}<extra></extra> ', # hovertemplate=None
        connectgaps=False, # this does nothing
    )

    fig.update_layout(hovermode="x")

    fig.update_xaxes(
        mirror=True,
        ticks="outside",
        showline=True,
        linecolor="black",
        gridcolor="lightgrey",
    )

    fig.update_yaxes(
        mirror=True,
        ticks="outside",
        showline=True,
        linecolor="black",
        gridcolor="lightgrey",
    )

    return await render_graph(fig, displaymodebar=False)


async def maptiler_satellite_v2(request, z: str, x: str, y: str) -> HttpResponse:
    # this function does two things:
    # - secure the maptiler_key
    # - save tiles in cache for some time
    maptiler_url = f"https://api.maptiler.com/tiles/satellite-v2/{z}/{x}/{y}.jpg?key={settings.MAPTILER_KEY}"
    title_data = await fetch_tile(url=maptiler_url, cache_timeout=60 * 60 * 24 * 7)  # 1 week
    return HttpResponse(title_data, content_type="image/jpeg")


async def osm_tiles(request, z: str, x: str, y: str) -> HttpResponse:
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    title_data = await fetch_tile(url=url, cache_timeout=60 * 60 * 24 * 7)  # 1 week
    return HttpResponse(title_data, content_type="image/png")


async def osm_buildings(request, z: str, x: str, y: str) -> HttpResponse:
    subdomains = ["a", "b", "c", "d"]
    s = random.choice(subdomains)
    url = f"https://{s}.data.osmbuildings.org/0.2/59fcc2e8/tile/{z}/{x}/{y}.json"
    title_data = await fetch_tile(url=url, cache_timeout=60 * 60 * 24 * 7)  # 1 week
    return HttpResponse(title_data, content_type="application/json")
