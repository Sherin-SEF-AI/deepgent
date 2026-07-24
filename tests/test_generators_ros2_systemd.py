"""ROS 2 node and systemd unit generators (WO-43). Pure, deterministic."""

from pathlib import Path

import pytest

from deepgent.generators import (
    Ros2NodeSpec,
    SystemdUnitSpec,
    scaffold_ros2_node,
    scaffold_systemd_unit,
)

pytestmark = pytest.mark.unit


def test_ros2_node_emits_buildable_package(tmp_path: Path) -> None:
    output = scaffold_ros2_node(Ros2NodeSpec(package="my pkg", node="Detector Node"))
    files = set(output.files)
    # package name is normalized to a python identifier.
    assert "my_pkg/package.xml" in files
    assert "my_pkg/setup.py" in files
    assert "my_pkg/my_pkg/detector_node.py" in files
    assert "my_pkg/resource/my_pkg" in files
    node_src = output.files["my_pkg/my_pkg/detector_node.py"]
    assert "class DetectorNode(Node)" in node_src
    assert "create_subscription" in node_src and "create_publisher" in node_src
    # entry point wires the console script.
    assert "detector_node = my_pkg.detector_node:main" in output.files["my_pkg/setup.py"]
    written = output.write(tmp_path)
    assert (tmp_path / "my_pkg" / "setup.py") in written


def test_ros2_node_topics_are_wired() -> None:
    output = scaffold_ros2_node(
        Ros2NodeSpec(package="p", node="n", sub_topic="camera/image", pub_topic="dets")
    )
    src = output.files["p/p/n.py"]
    assert '"camera/image"' in src and '"dets"' in src


def test_systemd_unit_basic() -> None:
    output = scaffold_systemd_unit(
        SystemdUnitSpec(name="deepgent-infer", exec_start="/opt/app/run", user="nvidia")
    )
    unit = output.files["deepgent-infer.service"]
    assert "[Unit]" in unit and "[Service]" in unit and "[Install]" in unit
    assert "ExecStart=/opt/app/run" in unit
    assert "User=nvidia" in unit
    assert "Restart=on-failure" in unit
    assert "Type=simple" in unit  # no watchdog


def test_systemd_watchdog_switches_to_notify() -> None:
    output = scaffold_systemd_unit(
        SystemdUnitSpec(name="svc", exec_start="/bin/x", watchdog_sec=30)
    )
    unit = output.files["svc.service"]
    assert "Type=notify" in unit
    assert "WatchdogSec=30" in unit
    assert any("sd_notify" in t for t in output.todos)


def test_systemd_rejects_bad_restart() -> None:
    with pytest.raises(ValueError):
        scaffold_systemd_unit(SystemdUnitSpec(name="x", exec_start="/y", restart="sometimes"))
