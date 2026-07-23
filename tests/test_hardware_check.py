"""Datasheet-grounded hardware conflict checker (#8). Pure, no hardware."""

import json
from pathlib import Path

import pytest

from deepgent.errors import TaskExecutionError
from deepgent.knowledge.hardware_check import (
    HardwareConfig,
    Peripheral,
    Rail,
    check_conflicts,
    load_config,
)

pytestmark = pytest.mark.unit


def test_no_conflicts() -> None:
    config = HardwareConfig(
        peripherals=(
            Peripheral("cam", pins=("GPIO7",), i2c_bus="i2c-1", i2c_addr=0x10, provenance="ds:cam"),
            Peripheral("imu", pins=("GPIO8",), i2c_bus="i2c-1", i2c_addr=0x68, provenance="ds:imu"),
        ),
    )
    report = check_conflicts(config)
    assert report.clean is True
    assert report.ungrounded == []


def test_pin_conflict() -> None:
    config = HardwareConfig(
        peripherals=(
            Peripheral("a", pins=("GPIO7",), provenance="ds"),
            Peripheral("b", pins=("GPIO7",), provenance="ds"),
        ),
    )
    report = check_conflicts(config)
    assert not report.clean
    assert report.conflicts[0].kind == "pin"
    assert set(report.conflicts[0].parties) == {"a", "b"}


def test_i2c_address_collision() -> None:
    config = HardwareConfig(
        peripherals=(
            Peripheral("x", i2c_bus="i2c-1", i2c_addr=0x40, provenance="ds"),
            Peripheral("y", i2c_bus="i2c-1", i2c_addr=0x40, provenance="ds"),
            Peripheral("z", i2c_bus="i2c-2", i2c_addr=0x40, provenance="ds"),  # different bus, ok
        ),
    )
    report = check_conflicts(config)
    kinds = [c.kind for c in report.conflicts]
    assert kinds == ["i2c"]
    assert "0x40" in report.conflicts[0].detail


def test_power_budget_overrun() -> None:
    config = HardwareConfig(
        peripherals=(
            Peripheral("a", rail="3v3", current_ma=600, provenance="ds"),
            Peripheral("b", rail="3v3", current_ma=600, provenance="ds"),
        ),
        rails=(Rail("3v3", budget_ma=1000),),
    )
    report = check_conflicts(config)
    assert any(c.kind == "power" for c in report.conflicts)
    power = next(c for c in report.conflicts if c.kind == "power")
    assert "1200mA" in power.detail and "1000mA" in power.detail


def test_power_within_budget() -> None:
    config = HardwareConfig(
        peripherals=(Peripheral("a", rail="3v3", current_ma=400, provenance="ds"),),
        rails=(Rail("3v3", budget_ma=1000),),
    )
    assert check_conflicts(config).clean


def test_ungrounded_flagged() -> None:
    config = HardwareConfig(peripherals=(Peripheral("nodocs", pins=("GPIO1",)),))
    report = check_conflicts(config)
    assert report.ungrounded == ["nodocs"]


def test_load_config(tmp_path: Path) -> None:
    data = {
        "peripherals": [
            {
                "name": "cam",
                "pins": ["GPIO7"],
                "i2c_bus": "i2c-1",
                "i2c_addr": "0x10",
                "rail": "3v3",
                "current_ma": 250,
                "provenance": "IMX219 datasheet p.12",
            },
        ],
        "rails": [{"name": "3v3", "budget_ma": 2000}],
    }
    config = load_config(json.dumps(data))
    assert config.peripherals[0].i2c_addr == 0x10
    assert config.peripherals[0].provenance is not None
    assert config.rails[0].budget_ma == 2000
    assert check_conflicts(config).clean


def test_load_config_requires_peripherals() -> None:
    with pytest.raises(TaskExecutionError):
        load_config(json.dumps({"rails": []}))


def test_report_render_and_dict() -> None:
    config = HardwareConfig(
        peripherals=(
            Peripheral("a", pins=("P1",), provenance="ds"),
            Peripheral("b", pins=("P1",), provenance="ds"),
        ),
    )
    report = check_conflicts(config)
    assert "CONFLICTS" in report.render()
    assert report.to_dict()["clean"] is False
