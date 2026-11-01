"""Kaaran: AI data analyst for Block and District Education Officers."""

import os

# openpyxl writes different (equally valid) XML bytes when lxml is installed (some optional tools pull it in).
# The synthetic generator promises byte-identical files per seed, so pin openpyxl's pure-Python writer.
os.environ.setdefault("OPENPYXL_LXML", "False")

__version__ = "0.1.0"
