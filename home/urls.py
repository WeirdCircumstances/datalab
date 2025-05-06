from django.urls import path

from .views import (
    draw_graph,
    hexmap,
    erfrischungskarte,
    show_by_tag,
    maptiler_satellite_v2,
    osm_tiles,
    osm_buildings,
    single,
    url_string_generator, erfrischungskarte_animation,
)

urlpatterns = [
    path("s/", single, name="single"),
    path("url_string_generator", url_string_generator, name="url_string_generator"),
    path("draw_graph/<sensebox_id>", draw_graph, name="draw_graph"),
    path("hexmap", hexmap, name="draw_hexmap"),
    path("s/hexmap", hexmap, name="single_hexmap"),
    path("erfrischungskarte/<str:this_time>/", erfrischungskarte, name="erfrischungskarte"),
    path("s/erfrischungskarte/<str:this_time>/", erfrischungskarte, name="single_erfrischungskarte"),
    path('erfrischungskarte_animation/', erfrischungskarte_animation, name='erfrischungskarte_animation'),
    path("show_by_tag/<str:box>", show_by_tag, name="show_by_tag"),
    path("s/show_by_tag/<str:box>", show_by_tag, name="single_show_by_tag"),
    path(
        "maptiler_satellite_v2/<str:z>/<str:x>/<str:y>", maptiler_satellite_v2, name="maptiler_satellite_v2"
    ),  # str not int -> no data transformation!
    path("osm_tiles/<str:z>/<str:x>/<str:y>", osm_tiles, name="osm_tiles"),
    path("osm_buildings/<str:z>/<str:x>/<str:y>", osm_buildings, name="osm_buildings"),
]
