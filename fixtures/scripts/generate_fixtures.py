#!/usr/bin/env python3  # noqa: D100

from os import path
from typing import List

from django.core.management import call_command

FIXTURES = [
    {
        "name": "1000_secrets.json",
        "models": ["extras.secret", "extras.secretsgroup"],
    },
    {
        "name": "1100_locations.json",
        "models": ["tenancy.tenant", "dcim.locationtype", "dcim.location"],
    },
]


def generate_fixtures(fixture_filename: str, models: List[str], needs_foreign_key=False):
    """Call the dumpdata command for the list of models.

    If `needs_foreign_key` is `False`, then add the `--natural-primary` argument
    to the command.
    """
    kwargs = {
        "format": "json",
        "indent": 2,
        "natural_foreign": True,
        "natural_primary": not needs_foreign_key,
        "output": fixture_filename,
    }

    call_command("dumpdata", *models, **kwargs)


def run(*args):
    """Run the script.

    This script has no optional arguments.
    """
    for fixture_file in FIXTURES:
        print("Generating", fixture_file["name"])
        fixture_filename = path.join(path.dirname(__file__), "..", fixture_file["name"])
        generate_fixtures(fixture_filename, fixture_file["models"], fixture_file.get("needs_primary_key", False))
