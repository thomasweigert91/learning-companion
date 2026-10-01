#!/usr/bin/env python
"""Kommandozeilen-Werkzeug fuer administrative Aufgaben."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learning_companion.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django konnte nicht importiert werden. Ist es installiert und ist "
            "das Virtualenv aktiviert?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
