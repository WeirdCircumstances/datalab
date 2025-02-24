#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    # only for debug:
    #
    # print("Python Path:", sys.path)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "datalab.settings.dev")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
