from django.urls import path

from .views import draw_graph, draw_hexmap, erfrischungskarte, show_by_tag, maptiler_satellite_v2, osm_tiles, osm_buildings

urlpatterns = [
    path('draw_graph/<sensebox_id>/', draw_graph, name='draw_graph'),
    path('draw_hexmap/<str:kind>', draw_hexmap, name='draw_hexmap'),
    #path('multi_map/', multi_map, name='multi_map'),
    path('erfrischungskarte/<str:this_time>/', erfrischungskarte, name='erfrischungskarte'),
    #path('cache_clear/', cache_clear, name='cache_clear'),
    path('show_by_tag/<str:box>', show_by_tag, name='show_by_tag'),
    path('maptiler_satellite_v2/<str:z>/<str:x>/<str:y>', maptiler_satellite_v2, name='maptiler_satellite_v2'), # str not int -> no data transformation!
    path('osm_tiles/<str:z>/<str:x>/<str:y>', osm_tiles, name='osm_tiles'),
    path('osm_buildings/<str:z>/<str:x>/<str:y>', osm_buildings, name='osm_buildings'),
]
