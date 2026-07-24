"""Board-type catalog (categorical profiles, no fabricated specs)."""

import pytest

from deepgent.boards import (
    BOARD_CATALOG,
    families,
    get_profile,
    list_catalog,
    render_catalog,
    suggest_capabilities,
)
from deepgent.boards.catalog import FAMILIES

pytestmark = pytest.mark.unit


def test_catalog_covers_the_requested_families() -> None:
    fam = set(families())
    assert {"jetson", "raspberry-pi", "accelerator", "host"} <= fam
    ids = {p.id for p in BOARD_CATALOG}
    assert {"jetson-agx-orin", "jetson-orin-nano", "jetson-nano"} <= ids  # Jetson series
    assert {"raspberry-pi-5", "raspberry-pi-4", "raspberry-pi-cm5"} <= ids  # Pi models
    assert {"hailo-8-ai-hat", "hailo-8l-ai-kit", "coral-usb"} <= ids  # AI HAT / accelerators


def test_every_profile_is_categorical_and_has_verify() -> None:
    for p in BOARD_CATALOG:
        assert p.family in FAMILIES
        assert p.toolchain and p.accelerator and p.interfaces
        # The prime directive: each entry tells the user to verify real specs.
        assert p.verify


def test_list_catalog_filter() -> None:
    jetsons = list_catalog("jetson")
    assert jetsons and all(p.family == "jetson" for p in jetsons)
    assert list_catalog("nonexistent") == []


def test_get_profile_and_capabilities() -> None:
    assert get_profile("nope") is None
    orin = get_profile("jetson-agx-orin")
    assert orin is not None and "cuda" in suggest_capabilities("jetson-agx-orin")
    assert "hailo" in suggest_capabilities("hailo-8-ai-hat")
    assert "csi" in suggest_capabilities("raspberry-pi-5")


def test_render_catalog() -> None:
    text = render_catalog(list_catalog())
    assert "jetson-agx-orin" in text and "Categorical only" in text
