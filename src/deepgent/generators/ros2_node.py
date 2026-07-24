"""Deterministic ROS 2 (ament_python) node scaffold.

Generators are preferred over LLM synthesis (prime directive: deterministic
first). This emits a complete, buildable ament_python package: package.xml,
setup.py/cfg, the resource marker, and a rclpy node with a timer-driven
publisher and a subscriber. No hardware facts are asserted; the distro is
whatever the caller passes (validated against versions.toml elsewhere).
"""

import re
from dataclasses import dataclass

from deepgent.generators.driver_scaffold import ScaffoldOutput

_IDENT = re.compile(r"[^a-z0-9_]")


def _pkg_ident(name: str) -> str:
    ident = _IDENT.sub("_", name.lower()).strip("_")
    if not ident or ident[0].isdigit():
        ident = f"pkg_{ident}"
    return ident


def _class_name(node: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", node)
    return "".join(p.capitalize() for p in parts if p) or "Node"


@dataclass(frozen=True)
class Ros2NodeSpec:
    """What to generate: a package, a node, and the topics it uses."""

    package: str
    node: str
    sub_topic: str = "input"
    pub_topic: str = "output"
    maintainer: str = "deepgent"
    maintainer_email: str = "deepgent@example.invalid"


def scaffold_ros2_node(spec: Ros2NodeSpec) -> ScaffoldOutput:
    """Generate a complete ament_python package for one node."""
    pkg = _pkg_ident(spec.package)
    node = _pkg_ident(spec.node)
    cls = _class_name(spec.node)

    package_xml = f"""<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>{pkg}</name>
  <version>0.0.1</version>
  <description>{spec.node} node scaffolded by deepgent.</description>
  <maintainer email="{spec.maintainer_email}">{spec.maintainer}</maintainer>
  <license>Apache-2.0</license>

  <depend>rclpy</depend>
  <depend>std_msgs</depend>

  <test_depend>ament_copyright</test_depend>
  <test_depend>ament_flake8</test_depend>
  <test_depend>ament_pep257</test_depend>
  <test_depend>python3-pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
"""

    setup_py = f"""from setuptools import find_packages, setup

package_name = "{pkg}"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="{spec.maintainer}",
    maintainer_email="{spec.maintainer_email}",
    description="{spec.node} node scaffolded by deepgent.",
    license="Apache-2.0",
    entry_points={{
        "console_scripts": [
            "{node} = {pkg}.{node}:main",
        ],
    }},
)
"""

    setup_cfg = f"""[develop]
script_dir=$base/lib/{pkg}
[install]
install_scripts=$base/lib/{pkg}
"""

    node_py = f'''"""{spec.node}: a rclpy node scaffolded by deepgent."""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class {cls}(Node):
    """Subscribes to '{spec.sub_topic}', republishes to '{spec.pub_topic}' on a timer."""

    def __init__(self) -> None:
        super().__init__("{node}")
        self._pub = self.create_publisher(String, "{spec.pub_topic}", 10)
        self._sub = self.create_subscription(String, "{spec.sub_topic}", self._on_msg, 10)
        self._timer = self.create_timer(1.0, self._on_timer)
        self._last = ""
        self.get_logger().info("{node} up")

    def _on_msg(self, msg: String) -> None:
        self._last = msg.data

    def _on_timer(self) -> None:
        out = String()
        out.data = f"processed: {{self._last}}"
        self._pub.publish(out)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = {cls}()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
'''

    return ScaffoldOutput(
        files={
            f"{pkg}/package.xml": package_xml,
            f"{pkg}/setup.py": setup_py,
            f"{pkg}/setup.cfg": setup_cfg,
            f"{pkg}/resource/{pkg}": "",
            f"{pkg}/{pkg}/__init__.py": "",
            f"{pkg}/{pkg}/{node}.py": node_py,
        },
        todos=[
            f"build in the ros2 container: colcon build --packages-select {pkg}",
            f"remap topics at launch if '{spec.sub_topic}'/'{spec.pub_topic}' collide",
            "replace std_msgs/String with the real message type for this pipeline",
        ],
    )
