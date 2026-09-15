from collections.abc import Sequence
from itertools import pairwise


def polygon_centroid(rings: Sequence[Sequence[Sequence[float]]]) -> tuple[float, float] | None:
    """Return the area-weighted (longitude, latitude) centroid of ArcGIS polygon rings."""
    weighted_longitude = 0.0
    weighted_latitude = 0.0
    signed_area_twice = 0.0

    for ring in rings:
        if len(ring) < 4:
            continue
        ring_area_twice = 0.0
        longitude_moment = 0.0
        latitude_moment = 0.0
        for start, end in pairwise(ring):
            longitude, latitude = start[:2]
            next_longitude, next_latitude = end[:2]
            cross = longitude * next_latitude - next_longitude * latitude
            ring_area_twice += cross
            longitude_moment += (longitude + next_longitude) * cross
            latitude_moment += (latitude + next_latitude) * cross
        if ring_area_twice:
            weighted_longitude += longitude_moment / 3
            weighted_latitude += latitude_moment / 3
            signed_area_twice += ring_area_twice

    if not signed_area_twice:
        return None
    return weighted_longitude / signed_area_twice, weighted_latitude / signed_area_twice
