#!/usr/bin/env python3  # noqa: D100

import json
from os import listdir, path

from django.apps import apps
from django.core.management import call_command
from django.db.models import ProtectedError

from nautobot.core.models.tree_queries import TreeModel


def delete(fixture_file):
    """Delete all of the objects for apps/models in a fixture file.

    This function will scan a fixture file and determine all of the apps
    and model types that are in the file. The function will then delete
    all of the models for each app (all of them, not just the instances
    in the fixture file) in the reverse order of what is specified in the
    fixture file.

    For instance, consider a fixture file that has the following models (in order):
        1. dcim.manufacturer
        2. dcim.devicetype
        3. dcim.device

    The `delete` function will essentially perform the following:
        1. `Device.objects.all().delete()`
        2. `DeviceType.objects.all().delete()`
        3. `Manufacturer.objects.all().delete()`

    The reason for reverse order is to attempt to work around database integrity violations
    by removing objects with foreign keys before removing the associated objects.
    """
    with open(fixture_file) as file:
        data = json.load(file)
        last_model = None
    for record in reversed(data):
        if last_model != record["model"]:
            model = apps.get_model(*record["model"].split("."))
            print("\tClearing", record["model"])
            if issubclass(model, TreeModel):
                model.objects.filter(parent__isnull=True).delete()
            else:
                queryset = model.objects.all()
                try:
                    queryset.delete()
                except ProtectedError:
                    queryset._raw_delete(queryset.db)
        last_model = record["model"]


def load(fixture_file):
    """Load a fixture file.

    This function essentially just runs `nautobot-server loaddata ./fixture/file`.
    """
    print("Loading", fixture_file)
    call_command("loaddata", fixture_file)


def run(*args):
    """Run the script.

    This script has no optional arguments.
    """
    fixtures_path = path.join(path.dirname(__file__), "..")
    fixtures = [fixture_file for fixture_file in listdir(fixtures_path) if fixture_file.endswith("json")]
    fixtures.sort()
    for fixture_file in reversed(fixtures):
        delete(fixture_file)
    for fixture_file in fixtures:
        load(fixture_file)
