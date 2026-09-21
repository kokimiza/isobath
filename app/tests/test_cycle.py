from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

from isobath.cycle import current_cutoff, iso, next_cutoff
from isobath.nightly import density_map

JST = ZoneInfo("Asia/Tokyo")


def test_window_boundary_is_0100_jst():
    assert iso(current_cutoff(datetime(2030, 3, 15, 0, 59, 59, 999999, tzinfo=JST))) == (
        "2030-03-13T16:00:00Z"  # still the window that started 3/14 01:00
    )
    assert iso(current_cutoff(datetime(2030, 3, 15, 1, 0, tzinfo=JST))) == "2030-03-14T16:00:00Z"
    assert iso(next_cutoff(datetime(2030, 3, 15, 1, 0, tzinfo=JST))) == "2030-03-15T16:00:00Z"


def test_density_suppresses_small_cells():
    points = np.array([[0.1, 0.1]] * 3 + [[2.0, -2.0]])
    grid = np.array(density_map(points, k=2)["counts"])
    assert grid.sum() == 3  # the lone point is hidden
    assert np.array(density_map(np.empty((0, 2)), k=2)["counts"]).sum() == 0
