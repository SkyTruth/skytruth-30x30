import json
from functools import lru_cache
import os
import pandas as pd


@lru_cache()
def load_iso_mapping():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(f"{base}/data/iso_map.json") as f:
        iso_map = json.load(f)
    return iso_map


@lru_cache()
def load_country_mapping():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(f"{base}/data/country_map.json") as f:
        iso_map = json.load(f)
    return iso_map


@lru_cache()
def load_regions():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(f"{base}/data/regions_data.json") as f:
        regions = json.load(f)
    return regions


@lru_cache()
def load_locations_code():
    base = os.path.dirname(os.path.abspath(__file__))
    return pd.read_csv(f"{base}/data/locations_code.csv", keep_default_na=False)
