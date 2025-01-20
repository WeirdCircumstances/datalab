import ast
import json
import os
import random
import time
from urllib.parse import urlparse

import math
import numpy as np
import plotly
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
import requests
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from influxdb_client import InfluxDBClient
from plotly.subplots import make_subplots
from pyproj import Transformer

from core.tools import (
    influx_org,
    influx_url,
    influx_token,
    influx_bucket,
    SenseBoxTable,
    mapbox_token,
    pd,
    get_timeframe,
    get_latest_boxes_with_distance_as_df,
    run_multithreaded,
    calculate_centroid,
    fetch_tile,
    settings,
)

# function to render graph with the same settings every time
async def render_graph(fig):
    return plotly.offline.plot(fig,
                               include_plotlyjs=False,
                               output_type='div',
                               #image_width='100%',
                               image_height='100%',
                               auto_open=False,
                               # https://plotly.com/python/configuration-options/
                               config={
                                   'displayModeBar': True,
                                   'displaylogo': False,
                                   'responsive': True,
                                   'modeBarButtonsToRemove': [
                                       'autoScale',
                                       'zoom',
                                       'pan',
                                       'toImage',
                                       'resetViewMapbox',
                                       'select',
                                       'toggleHover',
                                       'lasso2d',
                                       'pan2d',
                                       'select2d',
                                   ],
                               })

#@cache_page(60 * 59)
async def draw_graph(request, sensebox_id: str):
    ###########################################################
    # read influx
    ###########################################################

    # kind = 'test'

    query = f"""from(bucket: "{influx_bucket}")
    |> range(start:-3d, stop: now())
    |> filter(fn: (r) => r._measurement == "{sensebox_id}")
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
    """

    # |> filter(fn: (r) => r["_field"] == "Temperatur" or r["_field"] == "Beleuchtungsstärke" or r["_field"] == "Luftdruck" or r["_field"] == "PM10" or r["_field"] == "PM2.5" or r["_field"] == "UV-Intensität" or r["_field"] == "rel. Luftfeuchte" or r["_field"] == "location")|> yield(name: "mean")
    # |> keep(columns: ["_time", "_value", "Temperatur", "Beleuchtungsstärke"])

    client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org, debug=False)
    system_stats = client.query_api().query_data_frame(org='HU', query=query)

    df = system_stats

    df = df.drop(columns=['result', '_measurement', '_start', '_stop', 'table'])
    column_list = df.columns.to_list()
    column_list.remove('_time')

    df['_time'] = df['_time'].dt.round(freq='5min').dt.tz_convert(tz='Europe/Berlin')

    df = df.drop_duplicates()

    ###########################################################
    # draw graph
    ###########################################################

    # print(df.columns.tolist())

    # column_names = {'Temperatur': '°C', 'rel. Luftfeuchte': '%', 'Luftdruck': 'hPa', 'Beleuchtungsstärke': 'lux',
    #                 'UV-Intensität': 'W/m2', 'PM10': 'PM10', 'PM2.5': 'PM2.5',
    #                 'CO₂': 'CO2'}

    rows = len(column_list)

    fig = make_subplots(
        rows=rows,
        cols=1,
        # vertical_spacing=(1 / (rows - 1)), # Vertical spacing cannot be greater than (1 / (rows - 1)) = 0.062500
        # shared_xaxes=True,
        subplot_titles=column_list,
    )

    row = 0
    for item in column_list:
        row += 1
        print(item)
        fig.add_trace(
            go.Scatter(x=list(df['_time']), y=df[item], mode='lines', name=item),
            row=row, col=1
        )

    fig.update_yaxes(autorange=True)
    # fig.update_layout(
    #     xaxis1=dict(
    #         rangeselector=dict(
    #             buttons=list([
    #                 dict(count=1,
    #                      label="1m",
    #                      step="month",
    #                      stepmode="backward"),
    #                 # dict(count=6,
    #                 #     label="6m",
    #                 #     step="month",
    #                 #     stepmode="backward"),
    #                 # dict(count=1,
    #                 #     label="YTD",
    #                 #     step="year",
    #                 #     stepmode="todate"),
    #                 # dict(count=1,
    #                 #     label="1y",
    #                 #     step="year",
    #                 #     stepmode="backward"),
    #                 dict(step="all")
    #             ])
    #         ),
    #         rangeslider=dict(
    #             visible=False
    #         ),
    #         type="date"
    #     ),
    #     # xaxis8_rangeslider_visible=True,
    #     # xaxis8_type="date"
    # )

    sensebox = await SenseBoxTable.objects.aget(sensebox_id=sensebox_id)

    fig.update_layout(
        autosize=True,
        height=800,
        #width=1000,
        title_text=f"Werte von {sensebox.name}"
    )

    fig.update_traces(
        hoverinfo="y+name+x",
        # line={"width": 0.1},
        # marker={"size": 2},
        # mode="lines+markers",
        showlegend=False
    )

    #graph = plotly.offline.plot(fig, include_plotlyjs=False, output_type='div')
    graph = await render_graph(fig)

    return HttpResponse(graph)



# @cache_page(60 * 59)
async def draw_hexmap(request, kind: str = 'temp'):
    query = f"""from(bucket: "{influx_bucket}")
        |> range(start: -48h, stop: now())
        |> filter(fn: (r) => r["_field"] == "Temperatur" or r["_field"] == "PM10" or r["_field"] == "PM2.5")
        |> yield(name: "mean")
        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
    """

    client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org, debug=False)
    system_stats = client.query_api().query_data_frame(org='HU', query=query)

    # ToDo: sytem_stats empty -> no data fetched (show a message)

    df = pd.concat(system_stats,ignore_index=True, join='outer', axis=0)  # .groupby('_time', axis=0)

    df = df.drop(columns=['_start', '_stop', 'table', 'result'])

    id_and_location_dict = {}

    async for entry in SenseBoxTable.objects.all():
        id_and_location_dict[entry.sensebox_id] = [float(entry.location_latitude), float(entry.location_longitude)]

    def add_latitude(row):
        sensor_id = row['_measurement']
        return id_and_location_dict[sensor_id][0] if sensor_id in id_and_location_dict.keys() else None

    def add_longitude(row):
        sensor_id = row['_measurement']
        return id_and_location_dict[sensor_id][1] if sensor_id in id_and_location_dict.keys() else None

    df['latitude'] = df.apply(add_latitude, axis=1)
    df['longitude'] = df.apply(add_longitude, axis=1)

    df.dropna(inplace=True, subset=['latitude', 'longitude'])

    df['_time'] = df['_time'].dt.round(freq='60min').dt.tz_convert(tz='Europe/Berlin')

    px.set_mapbox_access_token(mapbox_token)

    if kind == 'temp':

        df.dropna(inplace=True, subset=['Temperatur'])

        # Remove values, that are way off the limit and are probably wrong!
        median = df['Temperatur'].median()  # mean()
        df = df[(df['Temperatur'] >= 0.1 * median) & (
                df['Temperatur'] <= 10 * median)]  # mehr als 1000 % vom Median (oder Mittelwert)

        fig = ff.create_hexbin_mapbox(
            data_frame=df, lat='latitude', lon='longitude', color='Temperatur',
            nx_hexagon=15,  # smaler numbers -> bigger hexagons
            opacity=0.7, labels={'color': '°C'}, animation_frame='_time',
            min_count=1, agg_func=np.mean, show_original_data=True,
            original_data_marker=dict(size=4, opacity=1.0, color='deeppink'),
            color_continuous_scale=px.colors.sequential.Turbo,
            zoom=10
        )

    else:

        df.dropna(inplace=True, subset=['PM10', 'PM2.5'])
        # df['Temperatur'] = df['Temperatur'].apply(lambda x: round(x, 2))
        # df.style.format({'Temperatur': '{:.2f}'})
        # df.to_csv('output.csv', index=False)

        fig = ff.create_hexbin_mapbox(
            data_frame=df, lat='latitude', lon='longitude', color='PM10',
            nx_hexagon=15, opacity=0.8, labels={'color': 'ppm'}, animation_frame='_time',
            min_count=1, agg_func=np.mean, show_original_data=True,
            original_data_marker=dict(size=4, opacity=1.0, color='deeppink'),
            color_continuous_scale=px.colors.sequential.GnBu,
            zoom=10, width=None, height=None,
        )

    fig.update_layout(
        autosize=True,
        #height=800,
        # width=100,
        # title_text=f"{'Temperatur der letzten 48 Stunden' if kind == 'temp' else 'Feinstaub der letzten 48 Stunden'}",
        mapbox_style='light',
        # 'open-street-map',  # 'basic', 'light', 'outdoors', 'carto-darkmatter', 'stamen-toner', 'stamen-watercolor', 'open-street-map', 'stamen-terrain'
        # https://plotly.com/python/tile-map-layers/
        margin=dict(b=0, t=30, l=0, r=0, pad=0),
        # style=dict(height='100vh')
        # autosize=True,

    )

    # fig.update_layout(
    #     legend=dict(
    #         yanchor="top",
    #         y=0.99,
    #         xanchor="left",
    #         x=0.01
    #     )
    # )

    # fig.update_yaxes(automargin=True)
    fig.layout.sliders[0].pad.t = 5
    fig.layout.sliders[0].pad.l = 0
    fig.layout.updatemenus[0].pad.t = 5
    fig.layout.updatemenus[0].pad.l = 0

    # fig.update_geos(fitbounds="locations")

    graph = await render_graph(fig)

    return HttpResponse(graph)


@cache_page(60 * 60 * 24)
async def erfrischungskarte(request, this_time='14Uhr'):
    color_sets = {'teal-red': [
        '#f0f0f0', '#e6c2c2', '#dc9494', '#d16666', '#c73838',  # Helle bis kräftige Rottöne
        '#d9eef4', '#cee0e4', '#bcd3d4', '#a7c3c4', '#90b3b4',  # Helle Teal-Töne
        '#a3cadb', '#97b7c3', '#8ca3ab', '#7f908f', '#6e7a73',  # Mittelhelle Blau-Teal-Töne
        '#71a6b5', '#66919c', '#597a82', '#4e6267', '#414a4b',  # Dunklere Blau-Töne
        '#408da0', '#367982', '#2b6464', '#1f4e46', '#143828'  # Dunkelgrüne bis fast Schwarztöne
    ],
        'green-blue': [
            # Unterste Zeile: Weiß zu Grün
            '#ffffff', '#e6ffe6', '#ccffcc', '#99ff99', '#66ff66',  # Helle Grün-Töne
            # 2. Zeile: Helle Blau- und Grün-Töne
            '#e6ffff', '#ccf2e6', '#b3e6cc', '#99d9b3', '#66cc99',  # Mischfarben mit Hauch von Blau-Grün
            # 3. Zeile: Mittelhelle Töne
            '#cceeff', '#b3e0ff', '#99d1ff', '#66b3ff', '#3399ff',  # Blau- und Grün-Mischungen
            # 4. Zeile: Intensivere Blau- und Grüntöne
            '#99ccff', '#80bfff', '#66b2ff', '#4da6ff', '#3399ff',  # Helle bis intensivere Blautöne
            # Oberste Zeile: Stärkste Blautöne
            '#66ccff', '#4db8ff', '#3399ff', '#1a82ff', '#0073e6'  # Dunkelblau
        ],
        'bg2': [
            '#FFFFFF', '#e2e5ec', '#c4cbd9', '#a7b1c6', '#8997B3',  # Verlauf nach Blau
            '#e2e7e3', '#E2E5EC', '       ', '       ', '       ',  # Mischung aus beiden Farbtönen
            '#c6d0c7', '       ', '#C4CBD9', '       ', '       ',  # Weiterer Verlauf von Grün-Blau
            '#a9b8ab', '       ', '       ', '#A7B1C6', '       ',  # Grüntöne mit gemischten Blautönen
            '#8ca08f', '       ', '       ', '       ', '#8CA08F'  # Mischung bis zum kräftigsten Wert
        ],
        # https://www.farbenundleben.de/webdesign/farbkombinationen_tool.htm
        'bg3': [
            '#FFFFFF', '#BFD9FF', '#80B3FF', '#408CFF', '#0066FF',  # Verlauf nach Blau
            '#BFD9BF', '#BFD9DF', '#80B3E0', '#408CDF', '#0066DF',  # Mischung aus beiden Farbtönen
            '#80B380', '#80B3A0', '#80B3C0', '#408CC0', '#0066C0',  # Weiterer Verlauf von Grün-Blau
            '#408C40', '#408C60', '#408C80', '#408CA0', '#0066A0',  # Grüntöne mit gemischten Blautönen
            '#006600', '#006620', '#006640', '#006660', '#006680'  # Mischung bis zum kräftigsten Wert
        ],
        'vorlage': [
            '       ', '       ', '       ', '       ', '       ',  # Y-Achse
            '       ', '       ', '       ', '       ', '       ',  #
            '       ', '       ', '       ', '       ', '       ',  #
            '       ', '       ', '       ', '       ', '       ',  #
            '       ', '       ', '       ', '       ', '       ',  # Mischung bis zum kräftigsten Wert
        ],
        'ygb': [
            '#FFFF00', '#BFCC40', '#809980', '#4066BF', '#0033FF',  # X-Achse
            '#BFCC00', '#BFCC20', '#809960', '#809960', '#608080',  #
            '#809900', '#809920', '#809940', '#608060', '#406680',  #
            '#406600', '#809920', '#608040', '#406660', '#204D80',  #
            '#003300', '#608020', '#406640', '#204D60', '#003380',  # Mischung bis zum kräftigsten Wert
        ],
        'bg4': [
            '#FFFFFF', '#BFE6FF', '#80CCFF', '#40B3FF', '#0099FF',  # X-Achse
            '#E6FFBF', '#D3F3DF', '#B3E6DF', '#93D9DF', '#73CCDF',  #
            '#CCFF80', '#C6F3C0', '#A6E6C0', '#86D9C0', '#66CCC0',  #
            '#B3FF40', '#B9F3A0', '#9AE6A0', '#7AD9A0', '#5ACCA0',  #
            '#99FF00', '#ACF380', '#8DE680', '#6DD980', '#4DCC80',  # Mischung bis zum kräftigsten Wert
        ],
        'jennifers_farben': [
            '#E6CCE6', '#AD99EC', '#7366F3', '#3A33F9', '#0000FF',  # X-Achse
            '#EC99AD', '#CD99CD', '#B080D0', '#9366D3', '#764DD6',  #
            '#F36673', '#D080B0', '#B366B3', '#974DB6', '#7A33B9',  #
            '#F9333A', '#D36693', '#B64D97', '#9A339A', '#7D1A9D',  #
            '#FF0000', '#D64D76', '#B9337A', '#9D1A7D', '#800080',  # Mischung bis zum kräftigsten Wert
        ],
        'jennifers_farben_bens_anpassung': [
            '#00CC00', '#009940', '#006680', '#0033BF', '#0000FF',  # Y-Achse
            '#409900', '#80E680', '#80B3C0', '#8080FF', '#3340BF',  #
            '#806600', '#C0B380', '#FFFFFF', '#B3C0C0', '#668080',  #
            '#BF3300', '#FF8080', '#F3C080', '#E6FF80', '#99BF40',  #
            '#FF0000', '#F24000', '#E68000', '#D9BF00', '#CCFF00',  # Mischung bis zum kräftigsten Wert
        ],
        'jennifers_farben_bens_anpassung_2': [
            '#800080', '#6000A0', '#4000C0', '#2000DF', '#0000FF',  # Y-Achse
            '#A00060', '#800080', '#6000A0', '#4000BF', '#2000DF',  #
            '#C00040', '#A00060', '#800080', '#6000A0', '#4000C0',  #
            '#DF0020', '#BF0040', '#A00060', '#800080', '#6000A0',  #
            '#FF0000', '#DF0020', '#C00040', '#A00060', '#800080',  # Mischung bis zum kräftigsten Wert
        ],
    }

    """
    Function to set default variables
    """

    def conf_defaults() -> dict:
        # Define some variables for later use
        default_conf = {
            'plot_title': 'Bivariate choropleth map using Ploty',  # Title text
            'plot_title_size': 9,  # Font size of the title
            'width': 1000,  # Width of the final map container
            'ratio': 0.8,  # Ratio of height to width
            'center_lat': 0,  # Latitude of the center of the map
            'center_lon': 0,  # Longitude of the center of the map
            'map_zoom': 3,  # Zoom factor of the map
            'map_style': 'open-street-map',
            'hover_x_label': 'Label x variable',  # Label to appear on hover
            'hover_y_label': 'Label y variable',  # Label to appear on hover
            'borders_width': 0.1,  # Width of the geographic entity borders
            'borders_color': '#f8f8f8',  # Color of the geographic entity borders

            # Define settings for the legend
            'top': 1,  # Vertical position of the top right corner (0: bottom, 1: top)
            'right': 1,  # Horizontal position of the top right corner (0: left, 1: right)
            'box_w': 0.03,  # Width of each rectangle
            'box_h': 0.03,  # Height of each rectangle
            'line_color': '#f8f8f8',  # '#f8f8f8',  # Color of the rectagles' borders
            'line_width': 0,  # Width of the rectagles' borders
            'legend_x_label': 'Higher x value',  # x variable label for the legend
            'legend_y_label': 'Higher y value',  # y variable label for the legend
            'legend_font_size': 11,  # Legend font size
            'legend_font_color': '#333',  # Legend font color

            'time': '14Uhr',
        }

        # Calculate height
        default_conf['height'] = default_conf['width'] * default_conf['ratio']

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
            if var == 'map_zoom':
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

    def load_geojson(geojson_url, local_file: str, data_dir: str ='refreshing_data'):
        # Make sure data_dir is a string
        data_dir = str(data_dir)

        # Set name for the file to be saved
        if not local_file:
            # Use original file name if none is specified
            url_parsed = urlparse(geojson_url)
            local_file = os.path.basename(url_parsed.path)
            print('Set name for local file.')
        else:
            pass
            # print(f'Local file name is {local_file}')

        geojson_file = data_dir + '/' + str(local_file)

        # Create folder for data if it does not exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            print('Created data folder!')
        else:
            pass
            # print('Data dir exists.')

        # Download GeoJSON in case it doesn't exist
        if not os.path.exists(geojson_file):
            print('Download file ...')

            # Make http request for remote file data
            geojson_request = requests.get(geojson_url)

            # Save file to local copy
            with open(geojson_file, 'wb') as file:
                file.write(geojson_request.content)

            print('Downloaded!')
        else:
            pass
            # print('Local file exists.')

        # print('try to load geojson')

        # Load GeoJSON file
        geojson = json.load(open(geojson_file, 'r'))

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
        for feature in geojson['features']:
            geom_type = feature['geometry']['type']

            if geom_type in ['Polygon', 'MultiPolygon', 'LineString', 'MultiLineString']:
                feature['geometry']['coordinates'] = transform_coordinates(feature['geometry']['coordinates'])

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

    def prepare_df(df, x='wind', y='temp'):
        # Check if arguments match all requirements
        if df[x].shape[0] != df[y].shape[0]:
            raise ValueError('ERROR: The list of x and y coordinates must have the same length.')

        new_df = df
        new_df.dropna(inplace=True)
        new_df[x] = new_df[x].astype('int') - 1
        new_df[y] = new_df[y].astype('int') - 1

        # print('before replacement')
        # print(new_df.head())

        # Replace values in temp to match legend
        # new_df[y] = new_df[y].replace([0, 1, 3, 4], [4, 3, 1, 0])
        # new_df[x] = new_df[x].replace({0: 4, 1: 3})

        # print('after replacement')
        # print(new_df.head())

        # Calculate the position of each x/y value pair in the 25-color matrix of bivariate colors
        new_df['biv_bins'] = [value_x + 5 * value_y for value_x, value_y in zip(new_df[x], new_df[y])]

        return new_df

    """
    Function to create a color square containig the 25 colors to be used as a legend
    """

    def create_legend(fig, colors, default_conf=None):
        if default_conf is None:
            default_conf = conf_defaults()

        # print(f'orginal order: {colors[:]}')


        if len(colors) < 25:
            print(f'Len of colors not right (should be 25): {len(colors)}')

        # Reverse the order of colors
        legend_colors = colors[:]
        legend_colors.reverse()

        # print(f'reversed order: {legend_colors}')

        # Calculate coordinates for all 25 rectangles
        coord = []

        # Adapt height to ratio to get squares
        width = default_conf['box_w']
        height = default_conf['box_h']  # /default_conf['ratio']

        # Start looping through rows and columns to calculate corners the squares
        for row in range(1, 6):
            for col in range(1, 6):
                coord.append({
                    'x0': round(default_conf['right'] - (col - 1) * width, 2),
                    'y0': round(default_conf['top'] - (row - 1) * height, 2),
                    'x1': round(default_conf['right'] - col * width, 2),
                    'y1': round(default_conf['top'] - row * height, 2)
                })

        # print(coord)

        # Create shapes (rectangles)
        for i, value in enumerate(coord):
            # Add rectangle
            fig.add_shape(go.layout.Shape(
                type='rect',
                fillcolor=legend_colors[i],
                # label_text=i, # name the colors
                line=dict(
                    color=default_conf['line_color'],
                    width=default_conf['line_width'],
                ),
                xref='paper',
                yref='paper',
                xanchor='right',
                yanchor='top',
                x0=coord[i]['x0'],
                y0=coord[i]['y0'],
                x1=coord[i]['x1'],
                y1=coord[i]['y1'],
            ))

            # Add text for first variable
            fig.add_annotation(
                xref='paper',
                yref='paper',
                xanchor='left',
                yanchor='top',
                x=coord[24]['x1'],
                y=coord[24]['y1'],
                showarrow=False,
                text=default_conf['legend_x_label'] + ' ->',
                font=dict(
                    color=default_conf['legend_font_color'],
                    size=default_conf['legend_font_size'],
                ),
                borderpad=0,
            )

            # Add text for second variable
            fig.add_annotation(
                xref='paper',
                yref='paper',
                xanchor='right',
                yanchor='bottom',
                x=coord[24]['x1'],
                y=coord[24]['y1'],
                showarrow=False,
                text=default_conf['legend_y_label'] + ' ->',
                font=dict(
                    color=default_conf['legend_font_color'],
                    size=default_conf['legend_font_size'],
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

    def create_bivariate_map(df, colors, geojson, x='wind', y='temp', ids='id', name='name', default_conf=None):
        if default_conf is None:
            default_conf = conf_defaults()
        if len(colors) != 25:
            raise ValueError('ERROR: The list of bivariate colors must have a length eaqual to 25.')

        # Recalculate values if width differs from default
        if not default_conf['width'] == 1000:
            default_conf = recalc_vars(default_conf['width'], ['map_zoom'], default_conf)  # 'height', 'plot_title_size', 'legend_font_size',

        # Prepare the dataframe with the necessary information for our bivariate map
        df_plot = prepare_df(df, x, y)

        # print(df_plot.head())
        # print(df_plot)

        # Create the figure
        fig = go.Figure(go.Choroplethmapbox(
            geojson=geojson,
            locations=df_plot[ids],
            z=df_plot['biv_bins'],
            marker_line_width=.5,
            colorscale=[[i / 24, colors[i]] for i in range(25)],
            # colorscale='Hot',
            customdata=df_plot[['id', 'wind', 'temp', 'biv_bins']],  # Add data to be used in hovertemplate
            hovertemplate='<br>'.join([  # Data to be displayed on hover
                '<b>%{customdata[0]}</b>',
                default_conf['hover_x_label'] + ': %{customdata[1]}',
                default_conf['hover_y_label'] + ': %{customdata[2]}',
                'MV: %{customdata[3]}',
                '<extra></extra>',  # Remove secondary information
            ])
        ))

        # Add some more details
        fig.update_layout(
            title=dict(
                text=default_conf['plot_title'],
                font=dict(
                    size=default_conf['plot_title_size'],
                ),
            ),
            mapbox_style='white-bg',
            # width=default_conf['width'],
            # height=default_conf['height'],
            autosize=True,
            mapbox=dict(
                center=dict(lat=default_conf['center_lat'], lon=default_conf['center_lon']),  # Set map center
                zoom=default_conf['map_zoom']  # Set zoom
            ),
        )

        fig.update_traces(
            marker_line_width=default_conf['borders_width'],  # Width of the geographic entity borders
            marker_line_color=default_conf['borders_color'],  # Color of the geographic entity borders
            showscale=False,  # Hide the colorscale
        )

        # Add the legend
        fig = create_legend(fig, colors, default_conf)

        return fig

    def custom_conf(this_time):
        # Load conf defaults
        custom_conf = conf_defaults()

        # Override some variables
        custom_conf['plot_title'] = 'Berliner Erfrischungskarte'
        custom_conf['width'] = 1000  # Width of the final map container
        custom_conf['ratio'] = 0.8  # Ratio of height to width
        custom_conf['height'] = custom_conf['width'] * custom_conf['ratio']  # Width of the final map container
        custom_conf['center_lat'] = 52.516221  # Latitude of the center of the map
        custom_conf['center_lon'] = 13.3992  # Longitude of the center of the map
        custom_conf['map_zoom'] = 10  # Zoom factor of the map
        custom_conf['map_style'] = 'open-street-map',  # open-street-map
        custom_conf['hover_x_label'] = 'windig'  # Label to appear on hover
        custom_conf['hover_y_label'] = 'warm'  # Label to appear on hover

        # Define settings for the legend
        custom_conf['line_width'] = 0.5  # Width of the rectagles' borders
        custom_conf['legend_x_label'] = 'windiger'  # x variable label for the legend
        custom_conf['legend_y_label'] = 'wärmer'  # y variable label for the legend

        custom_conf['time'] = this_time

        return custom_conf

    def load_data(default_conf):
        # Define URL of the GeoJSON file
        wind_url = 'https://raw.github.com/technologiestiftung/erfrischungskarte-daten/main/Wind_Temperature/data/clean/t_Wind_9bis21.geojson'
        # Load GeoJSON file
        wind = load_geojson(wind_url, local_file='t_Wind_9bis21.geojson')

        # print('loaded wind')

        temp_url = 'https://raw.github.com/technologiestiftung/erfrischungskarte-daten/main/Wind_Temperature/data/clean/t_Temperatur_9bis21.geojson'
        # Load GeoJSON file
        temperature = load_geojson(temp_url, local_file='t_Temperatur_9bis21.geojson')

        # print('loaded temp')

        df_list = []
        for idx, feature in enumerate(wind['features']):
            # feature['id'] = f"{'idx': idx}, {'type': 'id'}"
            feature['id'] = idx
            df_list.append({'id': idx, 'wind': feature["properties"][default_conf['time']]})
        wind_df = pd.DataFrame(df_list)

        df_list = []
        for idx, feature in enumerate(temperature['features']):
            # feature['id'] = f"{'idx': idx}, {'type': 'id'}"
            feature['id'] = idx
            df_list.append({'id': idx, 'temp': feature["properties"][default_conf['time']]})
            # if feature["properties"]["14Uhr"] == 1.0:
            #    print(idx)
            # print(f'{idx}: {feature["properties"]["14Uhr"]}')
        temp_df = pd.DataFrame(df_list)

        bivariate_df = pd.merge(wind_df, temp_df, on='id')
        # bivariate_df.head()

        return wind, temperature, bivariate_df

    # Create our bivariate map
    custom_conf = custom_conf(this_time)
    wind, temperature, bivariate_df = load_data(default_conf=custom_conf)
    fig = create_bivariate_map(bivariate_df, color_sets['jennifers_farben'], wind, default_conf=custom_conf)

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

    return HttpResponse(graph)


@cache_page(60 * 1)
async def show_by_tag(request, region: str = 'Berlin', box: str = 'all') -> HttpResponse:
    """
    1. get_latest_boxes_with_distance_as_df() -> seems complex, but this is much faster to do so!
        (much faster than https://docs.opensensemap.org/#api-Measurements-getDataByGroupTag)
    2. get_boxes_with_tag(tagname) -> create a new df from filtered db
    3. run_multithreaded(df) -> get a list of df, concatenate them (they have the id in attr)
    """

    tag = request.GET.get('tag', 'HU Explorers')

    start_timer = time.time()

    #print(f':::::::::::::::::: 1 {time.time() - start_timer}')

    # ToDo: Satellitenkarte Stadia? https://leaflet-extras.github.io/leaflet-providers/preview/
    # df = get_boxes_with_tag(tag)

    df = await get_latest_boxes_with_distance_as_df(region)

    #print(df.info())

    #print(f':::::::::::::::::: 2 {time.time() - start_timer} - after: get_latest_boxes_with_distance_as_df(region)')

    # remove all boxes with empty grouptags
    df = df.dropna(subset=['grouptag'])

    found_grouptags = df['grouptag']

    # filter rows for "tag"
    df = df[df['grouptag'].apply(lambda x: tag in x)]

    #print(f':::::::::::::::::: 3 {time.time() - start_timer} - after: drop empty grouptags, check if selected tag is in the list of grouptags')

    tag_summary = []
    for taglist in found_grouptags:
        for this_tag in taglist:
            if this_tag != '' and this_tag != ' ':
                tag_summary.append(this_tag)
    found_grouptags = list(dict.fromkeys(tag_summary))  # remove double entries by convert it to dict and then to list again

    if df.empty:
        print('tag is empty')
        return render(request, template_name='home/sub_templates/dashboard_1.html', context={
            'box': box,
            'tag': tag,
            'no_results_for_tag': tag,
            'found_grouptags': found_grouptags,
        })

    # print(f":::::::::::::::::::::::::::::::::::::: filtered df \n{df.columns}")
    # print(df.head())
    print(df.info())

    # I've got get_latest_boxes_with_distance_as_df() and found all boxes with tag
    # Now I want to get all sensor data

    timeframe = await get_timeframe(1.0)  # this should be fixed: get_latest_boxes_with_distance_as_df(region) only returns data fpr today!
    # print(f"timeframe: {timeframe}")

    #print(f':::::::::::::::::: 4 {time.time() - start_timer} - after: check if selected grouptag is valid and is there any data for today')

    # results = list
    # ToDo: create test, if there are no results (timeframe to short ...)
    results = await run_multithreaded(df, timeframe)
    #results = asyncio.run(run_multithreaded(df, timeframe))

    #print(f':::::::::::::::::: len results {len(results)}')

    #print(f':::::::::::::::::: 5 {time.time() - start_timer} - after: run_multithreaded(df, timeframe)')

    # df structure: ['_id', 'createdAt', 'updatedAt', 'name', 'currentLocation', 'exposure', 'sensors', 'model', 'grouptag', 'image', 'weblink', 'description']
    # i don't need 'createdAt', 'updatedAt', 'exposure', 'image', 'weblink', 'description'
    # print(':::::::::::::::::::::::::::::::::::::: after dropping unnecessary columns:')
    df.drop(columns=['createdAt', 'updatedAt', 'exposure', 'image', 'weblink', 'description', 'model'], inplace=True)
    # print(df.head())
    # print(df.columns)

    #print(f':::::::::::::::::: 6 {time.time() - start_timer} after: drop some columns')

    combined_list = []

    for b_index, s_box in df.iterrows():  # get one box after another as pd.Series
        # create a dict to use it later to match sensor title with unit to display
        unit_dict = {}
        for s in s_box['sensors']:
            unit_dict[s['title']] = {'unit': s['unit'], 'sensorId': s['_id']}

        # a combined dict that will act as a row later in the df

        for r in results:  # get one sensor after another as df
            if s_box['_id'] == r.attrs['box_id']:  # check if this the box matches the one from the sensor df

                for s_index, s_sensor in r.iterrows():  # sensors now as Series

                    # from here on I read the sensor values
                    for item in s_sensor.items():  # iterate over series items
                        combined_dict = {
                            'createdAt': s_sensor.name,  # set datetime for all sensor reading (they come all at the same time)
                            'boxId': s_box['_id'],
                            'grouptag': s_box['grouptag'],
                            'name': s_box['name'],
                            'lat': s_box['currentLocation']['coordinates'][1],
                            'lon': s_box['currentLocation']['coordinates'][0],
                            'title': item[0],
                            'value': item[1],
                            'unit': unit_dict[item[0]]['unit'],
                            'sensorId': unit_dict[item[0]]['sensorId'],
                        }

                        # combined_dict['coordinates'] = s_box['currentLocation']['coordinates']  # box location

                        # print('::::::::::::::::::::::::::::::::::::::')
                        # print(combined_dict)

                        combined_list.append(combined_dict)  # append this new created dict (aka row) to the list

                    # combined_dict['sensorId'] = s_box['sensorId']

                    # print(s_sensor)
                    # print(type(s_sensor))

    # for d in combined_list:
    #    print(d['createdAt'])

    df = pd.DataFrame(combined_list)

    # print(df['createdAt'])

    #print(f':::::::::::::::::: 7 {time.time() - start_timer} - after: create a complete new df')

    # print(df['name'].unique())
    # print(df.columns)

    # convert createdAt to datetime
    df['createdAt'] = pd.to_datetime(df['createdAt'], format='%Y-%m-%dT%H:%M:%S.%fZ', utc=True)
    df['createdAt'] = df['createdAt'].dt.tz_convert(tz='Europe/Berlin')

    print(df['createdAt'].max())

    # round to minutes -> data becomes comparable for every minute
    # important, when data is collected and shown in one figure
    # df = df.set_index('createdAt')
    # df = df.drop(['createdAt'], axis=1)

    # sort for index, which is time, to make errors visible
    # df = df.sort_index()

    # ToDo Doku
    df['value'] = pd.to_numeric(df['value'])
    # df = df.set_index('createdAt')
    # df['mean_value'] = df.groupby(['createdAt', 'boxId', 'sensorId'])['value'].transform('mean').round(2)

    df = df.set_index('createdAt')

    #print(f':::::::::::::::::: 8 {time.time() - start_timer} - after: set index to createdAt')

    # # get most recent time and convert this to date only
    # most_recent_date = df.index.max()
    # # print(f'most_recent_date: {df.index.max()}')
    # start_time = most_recent_date.date()
    #
    # # keep only the last values
    # df = df[(df.index.date >= start_time)]
    #
    # # get most recent time and convert this to date only
    # most_recent_date = df.index.max()
    # start_time = most_recent_date.date()
    #
    # # keep only the last values
    # df = df[(df.index.date >= start_time)]

    # get all unique sensor_ids
    # sensor_id_list = df['sensorId'].unique()

    # get names (titles), units and other infos for the sensors
    # takes a long time!!!
    # > 30 sec
    # 1,6 sec
    # 75 sec
    # sensor_complete_list = []

    # for id in sensor_id_list:
    #    sensor_complete_list.append(get_sensor_data(df, id))

    # create df from that and rename colum to match the first df
    # df_sensor = pd.DataFrame(sensor_complete_list)
    # df_sensor.rename(columns={'_id': 'sensorId'}, inplace=True)
    # df_sensor.drop(columns='lastMeasurement', inplace=True)

    # copy index back to column
    # merge both df to get sensor_ids and titles together
    # set column again as index
    # df['createdAt'] = df.index
    # df = df.merge(df_sensor, on="sensorId", how="left")
    # df = df.set_index('createdAt')

    # convert value to numeric, to automaticly scale the y asxis correct
    # df['value'] = pd.to_numeric(df['value'])

    name_list = df['name'].unique()

    # ToDo Doku
    df_name_list = []
    for name in name_list:
        df_name_list.append(df[df['name'] == name])

    #print(f':::::::::::::::::: 9 {time.time() - start_timer} - after: get all unique box names')

    # calc mean for all boxes with same time and name. Keep all other columns!

    # ToDO Doku
    df_test = df

    # title = sensebox_id name
    # get the mean of all values over all sensors and boxes to show them in one figue
    df_test['value_avg'] = df_test.groupby([df_test.index, 'title'])['value'].transform('median').round(2)
    # reset the index
    # df_avg_all_boxes['value'] = pd.to_numeric(df_avg_all_boxes['value'])
    # df_test = df_test.sort_index()

    """ get latest values from this df for a certain sensebox. """

    #print(f':::::::::::::::::: 10 {time.time() - start_timer} - after: get madian of all boxes (improvement here?)')

    # show one or all boxes
    if box != 'all':
        single_box_df = df_test[df_test['name'] == box]
    else:
        single_box_df = df_test

    # print(single_box_df.columns)
    # print(single_box_df.head())
    # print(single_box_df.shape)

    #print(f':::::::::::::::::: 11 {time.time() - start_timer} - after: check if one ore more boxes show be shown')

    # get all unique sensors
    sb_sensor_names_list = single_box_df['title'].unique()
    # print(len(sb_sensor_names_list))

    def draw_single_sensor_df_graph(df):
        fig = px.line(df, x=df.index, y='value',
                      labels={
                          'value': f'{df['title'].iloc[0]} ({df['unit'].iloc[0]})',
                          'createdAt': 'Zeit',
                      },)

        fig.update_layout(
            height=200,
            margin=dict(b=0, t=0, l=0, r=0, pad=0),
        )

        graph = plotly.offline.plot(fig,
                output_type='div',  # This is optional! If False, it will output a hole html file! (Perfect!)
                include_plotlyjs=False,  # This show be set to True then! Docu: https://plotly.com/python/interactive-html-export/
                image_width='100%',
                # image_height='1200',
                auto_open=False,
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                    'responsive': True,
                    'modeBarButtonsToRemove': [
                        'zoom',
                        'zoomIn',
                        'zoomOut',
                        'autoScale',
                        'resetScale',
                        'pan',
                        'toImage',
                        'resetViewMapbox',
                        'select',
                        'toggleHover',
                        'lasso2d',
                        'pan2d',
                        'select2d',
                    ],
                })

        return graph

    # show only the absolut last measured sensor value

    list_of_dicts_with_rows_and_graphs = []
    for sensor in sb_sensor_names_list:
        sensor_dict_row_and_graph = {}

        single_sensor_df = single_box_df[single_box_df['title'] == sensor]
        sensor_dict_row_and_graph['row'] = single_sensor_df[single_sensor_df.index == single_sensor_df.index.max()].to_dict('list')
        sensor_dict_row_and_graph['graph'] = draw_single_sensor_df_graph(single_sensor_df)
        list_of_dicts_with_rows_and_graphs.append(sensor_dict_row_and_graph)

        # print(latest_sensor_df_list)



    # print(f':::::::::::::::::: 12 {time.time() - start_timer} - after: get the last measured value for every box')

    # ToDo: better naming of df
    # reset index, so the function drop_duplicates can work
    df_test = df_test.reset_index()

    grouptags = df_test['grouptag'].iloc[0]
    # print(type(grouptag))
    if not isinstance(grouptags, list):
        grouptags = ast.literal_eval(grouptags)
        print(f"changed grouptag type from str to list: {grouptags}")



    #print(f':::::::::::::::::: 13 {time.time() - start_timer} - after: str -> list of grouptags')

    # ToDo: ONLY FOR TEST A HYPOTHESIS
    df_test = df_test.drop(columns=['grouptag'])

    # print(df_test.columns)
    # print(df_test.head())
    # print(df_test.shape)

    # drop dublicates of exactly the same values in the fields listed below

    # print(df_test.head())
    # print(df_test.dtypes)

    # for index, ser in df_test.iterrows():
    #    print(f"{index}: {ser['createdAt']} {ser['boxId']} {ser['name']} {ser['sensorId']} {ser['title']} {ser['value']} {ser['unit']} ")

    if not df_test[df_test.duplicated()].empty:
        print('cleaned df from duplicates')
        df_unique = df_test.drop_duplicates()  # subset=['createdAt', 'title', 'value_avg']
        # df_unique = df_test
    else:
        df_unique = df_test

    #print(f':::::::::::::::::: 14 {time.time() - start_timer} - after remove duplicates')

    # set time as index again (3rd time??)
    # df_unique['createdAt'] = df_unique['createdAt'].dt.tz_localize # tz_convert(tz='Europe/Berlin')

    df_unique = df_unique.set_index('createdAt')

    # print(df_unique.columns)
    # print(df_unique.head())
    # print(df_unique.shape)

    # All sensors in one figure!

    #pd.options.plotting.backend = "plotly"

    px_colors = px.colors.sequential.solar  # max 12 colors -> max 12 boxes
    colors = px.colors.sequential.solar  # ['red', 'blue', 'green', 'orange', 'purple']  # 5 colors -> 5 different sensors

    sensor_list = df_unique['title'].unique()

    fig = make_subplots(rows=len(sensor_list), cols=1, shared_xaxes=True, subplot_titles=sensor_list)

    # print(f':::::::::::::::::: 15 {time.time() - start_timer}')

    coordinates = []
    for i, row in df_unique.iterrows():
        coordinates.append({'lat': row['lat'], 'lon': row['lon']})

    lat, lon = calculate_centroid(coordinates=coordinates)

    """

    # Status 4.11.: ich möchte auch die anderen Werte in der Grafik darstellen. Dazu kann ich df_test benutzen. Die Farben kommen von px_colors
    # Nur noch die Liste klären ...

    # recognize all unique sensors (here 2)
    # add them as df to a list

    # j = 0  # thos counts the different senseBox sensors, I need initiate this here, to render the legend correct. See below: update_layout

    # df_all_other_sensors = []
    for i, sensor in enumerate(sensor_list):
        this_df = df_unique[df_unique['title'] == sensor]

        # print(f"{j} - {df_sensor['title'].iloc[0]}")

        # get boxes with the selected sensor and add the df to a list
        box_list = this_df['name'].unique()
        box_df_list = []
        for this_box in box_list:
            # print(type(box))
            if box == 'all':
                box_df_list.append(this_df[this_df['name'] == this_box])
        if len(box_df_list) == 0:
            box_df_list.append(this_df[this_df['name'] == box])

        # print(len(box_df_list))

        if this_df.shape[0] > 0:
            fig.add_trace(go.Scatter(
                x=this_df.index,
                y=this_df['value_avg'],
                name=f"{this_df['title'].iloc[0]} ({this_df['unit'].iloc[0]}) Mittelwert",
                mode='lines+markers',
                legendgroup=i + 1,
                marker=dict(
                    color=colors[(i + 3) % 11],
                    size=2,
                    line=dict(color=colors[(i + 3) % 11], width=1),
                ),
                line=dict(color=colors[(i + 3) % 11], width=1),
            ),
                row=i + 1,
                col=1,
            )  # color=df["sensorId"], hover_data=['name', 'title', 'unit'], marker=True

            for j, this_box in enumerate(box_df_list):
                if this_box.shape[0] > 0:  # if there is a sensor, that this box does not have
                    # print(box['name'].iloc[0])
                    # print(box.shape)

                    fig.add_trace(go.Scatter(
                        x=this_box.index,
                        y=this_box['value'],
                        opacity=0.2,
                        name=f"{this_box['title'].iloc[0]} ({this_box['unit'].iloc[0]}) {this_box['name'].iloc[0]}",
                        mode='lines+markers',
                        legendgroup=i + 1,
                        marker=dict(
                            color=px_colors[j * 2],
                            size=2,
                            line=dict(color=px_colors[j * 2], width=1),
                        ),
                        line=dict(color=px_colors[j * 2], width=1),  # max 12 colors
                    ),
                        row=i + 1,  # this is correct!
                        col=1,
                    )

    fig.update_layout(
        # autosize=True,
        height=1200,
        legend_tracegroupgap=1200 / (len(sensor_list) + 5.5),
    )

    print(len(sensor_list))
    print(1200 / len(sensor_list))

    # fig.update_layout(legend=dict(
    #     yanchor="top",
    #     y=0.99,
    #     xanchor="left",
    #     x=0.01
    # ))

    graph = plotly.offline.plot(fig,
                                output_type='div',  # This is optional! If False, it will output a hole html file! (Perfect!)
                                include_plotlyjs=False,  # This show be set to True then! Docu: https://plotly.com/python/interactive-html-export/
                                image_width='100%',
                                # image_height='1200',
                                auto_open=False,
                                config={
                                    'displayModeBar': True,
                                    'displaylogo': False,
                                    'responsive': True,
                                    'modeBarButtonsToRemove': [
                                        'zoom',
                                        'pan',
                                        'toImage',
                                        'resetViewMapbox',
                                        'select',
                                        'toggleHover',
                                        'lasso2d',
                                        'pan2d',
                                        'select2d',
                                    ],
                                })

    # context['graph'] = graph
    """

    # return HttpResponse(graph)

    #print(f':::::::::::::::::: 16 {time.time() - start_timer} - after: draw all graphs ')


    tag = tag.replace(' ', '+')

    return render(request, template_name='home/sub_templates/dashboard_1.html', context={
        #'graph': graph,
        'name_list': name_list,
        'list_of_dicts_with_rows_and_graphs': list_of_dicts_with_rows_and_graphs,
        'grouptag': grouptags,
        'box': box,  # box name
        'lat': lat,
        'lon': lon,
        'tag': tag,
        'found_grouptags': found_grouptags,
    })


async def maptiler_satellite_v2(request, z: str, x: str, y: str) -> HttpResponse:
    # this function does two things:
    # - secure the maptiler_key
    # - save tiles in cache for some time
    maptiler_url = f'https://api.maptiler.com/tiles/satellite-v2/{z}/{x}/{y}.jpg?key={settings.MAPTILER_KEY}'
    title_data = await fetch_tile(url=maptiler_url, cache_timeout=60 * 60 * 24 * 7)  # 1 week
    return HttpResponse(title_data, content_type="image/jpeg")

# https://tile.openstreetmap.org/{z}/{x}/{y}.png
async def osm_tiles(request, z: str, x: str, y: str) -> HttpResponse:
    url = f'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    title_data = await fetch_tile(url=url, cache_timeout=60 * 60 * 24 * 7)  # 1 week
    return HttpResponse(title_data, content_type="image/png")

async def osm_buildings(request, z: str, x: str, y: str) -> HttpResponse:
 subdomains = ['a', 'b', 'c', 'd']
 s = random.choice(subdomains)
 url = f'https://{s}.data.osmbuildings.org/0.2/59fcc2e8/tile/{z}/{x}/{y}.json'
 title_data = await fetch_tile(url=url, cache_timeout=60 * 60 * 24 * 7)  # 1 week
 return HttpResponse(title_data, content_type="application/json")
