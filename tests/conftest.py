from __future__ import annotations

import pytest

from forgecast.sample import generate_world


@pytest.fixture(scope="session")
def world():
    return generate_world()
