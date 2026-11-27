"""Shapes and expected areas shared by the integration tests."""

# A 1°x1° cell at the equator covers about 12,300 km²
MIN_DEGREE_CELL_KM2 = 11_000
MAX_DEGREE_CELL_KM2 = 14_000

# A 1°x1° cell at 50–51°N covers about 7,900 km²
MIN_DEGREE_CELL_AT_50N_KM2 = 7_500
MAX_DEGREE_CELL_AT_50N_KM2 = 8_300


def box(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def by_code(result: dict) -> dict[str, float]:
    return {area["code"]: area["added_area"] for area in result["locations"]}
