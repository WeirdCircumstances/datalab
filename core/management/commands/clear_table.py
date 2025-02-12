from django.core.management.base import BaseCommand

from home.models import SenseBoxTable, SensorsInfoTable, GroupTag


# from core.tools import *


class Command(BaseCommand):
    help = "Clear (delete) SenseBox table and SensorsInfoTable to get rid of inactive boxes."

    # def add_arguments(self, parser):
    #     parser.add_argument('--csv', type=str)

    def handle(self, *args, **options):
        t = SenseBoxTable.objects.all()
        t.delete()
        print("Deleted SenseBox table.")
        t = SensorsInfoTable.objects.all()
        t.delete()
        print("Deleted SensorsInfo table.")
        t = GroupTag.objects.all()
        t.delete()
        print("Deleted GroupTag table.")
