from django.contrib import admin

from home.models import *


@admin.register(SenseBoxTable)
class SenseBoxTableAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = (
        "sensebox_id",
        "name",
        "location_latitude",
        "location_longitude",
    )

    list_filter = (
        "sensebox_id",
        "name",
    )


@admin.register(SensorsInfoTable)
class SensorsInfoTable(admin.ModelAdmin):
    list_display = (
        "name",
        "unit",
    )

    list_filter = (
        "name",
        "unit",
    )


@admin.register(SenseBoxLocation)
class SenseBoxLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "location_latitude", "location_longitude", "maxDistance", "exposure")

    list_filter = ("name",)
