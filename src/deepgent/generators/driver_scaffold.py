"""Driver scaffolder: RAG-grounded V4L2/I2C skeleton + DT fragment (Tier 3).

Deterministic template generation (prime directive: a generator does the
step). Register addresses, I2C addresses, and bindings are NEVER invented:
they come from datasheet-rag chunks passed in, each carrying provenance.
Fields with no sourced value are emitted as explicit TODO markers with the
question to resolve, never as a plausible guess.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

_logger = structlog.get_logger(__name__)

_C_IDENT = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class RegisterFact:
    """One sourced register definition."""

    name: str
    address: str
    description: str
    provenance: str


@dataclass(frozen=True)
class DriverSpec:
    """Everything needed to scaffold one sensor driver."""

    device_name: str
    compatible: str
    i2c_address: str | None
    kind: str  # "v4l2" | "i2c"
    registers: tuple[RegisterFact, ...] = ()
    unresolved: tuple[str, ...] = ()  # open questions with no sourced value

    @property
    def c_ident(self) -> str:
        return _C_IDENT.sub("_", self.device_name.lower()).strip("_")


@dataclass
class ScaffoldOutput:
    """Generated files keyed by relative path."""

    files: dict[str, str] = field(default_factory=dict)
    todos: list[str] = field(default_factory=list)

    def write(self, root: Path) -> list[Path]:
        written = []
        for rel, content in self.files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            written.append(path)
        return written


def _register_defines(spec: DriverSpec) -> str:
    if not spec.registers:
        return "/* TODO: no registers sourced from datasheet-rag yet */"
    lines = []
    prefix = spec.c_ident.upper()
    for reg in spec.registers:
        suffix = _C_IDENT.sub("_", reg.name.lower()).strip("_").upper()
        macro = f"{prefix}_REG_{suffix}"
        lines.append(f"#define {macro} {reg.address}  /* {reg.description} [{reg.provenance}] */")
    return "\n".join(lines)


def _todo_block(spec: DriverSpec) -> str:
    if not spec.unresolved:
        return ""
    lines = ["", "/*", " * UNRESOLVED (no sourced value; do not guess):"]
    lines += [f" *   - {q}" for q in spec.unresolved]
    lines.append(" */")
    return "\n".join(lines)


def scaffold_i2c_driver(spec: DriverSpec) -> str:
    addr = spec.i2c_address if spec.i2c_address else "/* TODO: I2C address unsourced */"
    return f"""\
// SPDX-License-Identifier: GPL-2.0
// {spec.device_name} I2C driver skeleton (deepgent scaffold).
// Register values are datasheet-sourced with provenance; unsourced values
// are TODO markers, never invented.
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>

#define {spec.c_ident.upper()}_I2C_ADDR {addr}

{_register_defines(spec)}

struct {spec.c_ident}_priv {{
    struct i2c_client *client;
}};

static int {spec.c_ident}_probe(struct i2c_client *client)
{{
    struct {spec.c_ident}_priv *priv;

    priv = devm_kzalloc(&client->dev, sizeof(*priv), GFP_KERNEL);
    if (!priv)
        return -ENOMEM;
    priv->client = client;
    i2c_set_clientdata(client, priv);
    /* TODO: verify chip id register on hardware before trusting probe */
    return 0;
}}

static void {spec.c_ident}_remove(struct i2c_client *client)
{{
}}

static const struct of_device_id {spec.c_ident}_of_match[] = {{
    {{ .compatible = "{spec.compatible}" }},
    {{ }}
}};
MODULE_DEVICE_TABLE(of, {spec.c_ident}_of_match);

static struct i2c_driver {spec.c_ident}_driver = {{
    .driver = {{
        .name = "{spec.c_ident}",
        .of_match_table = {spec.c_ident}_of_match,
    }},
    .probe = {spec.c_ident}_probe,
    .remove = {spec.c_ident}_remove,
}};
module_i2c_driver({spec.c_ident}_driver);
{_todo_block(spec)}
MODULE_DESCRIPTION("{spec.device_name} driver (deepgent scaffold)");
MODULE_LICENSE("GPL v2");
"""


def scaffold_device_tree(spec: DriverSpec) -> str:
    addr = spec.i2c_address if spec.i2c_address else "0x00 /* TODO: sourced address */"
    reg = spec.i2c_address.replace("0x", "") if spec.i2c_address else "00"
    return f"""\
// {spec.device_name} device tree fragment (deepgent scaffold).
// Placement under the correct I2C bus node is board-specific: confirm the
// bus and any regulators/GPIOs against the carrier schematic.
&i2c_bus {{
    {spec.c_ident}@{reg} {{
        compatible = "{spec.compatible}";
        reg = <{addr}>;
        /* TODO: add clocks, supplies, reset-gpios per the carrier schematic */
        status = "okay";
    }};
}};
"""


def scaffold_driver(spec: DriverSpec) -> ScaffoldOutput:
    """Generate driver + device tree fragment for a sensor spec.

    Both v4l2 and i2c sensors are scaffolded from the same I2C control-plane
    skeleton; a v4l2 sensor additionally needs its subdev ops, which land as
    a TODO rather than a fabricated implementation.
    """
    output = ScaffoldOutput()
    output.files[f"drivers/{spec.c_ident}.c"] = scaffold_i2c_driver(spec)
    output.files[f"dts/{spec.c_ident}.dtsi"] = scaffold_device_tree(spec)
    output.todos = list(spec.unresolved)
    if spec.kind == "v4l2":
        output.todos.append(
            "v4l2 subdev ops (v4l2_subdev_video_ops/pad_ops) not scaffolded; "
            "implement against the sensor's mode table"
        )
    if spec.i2c_address is None:
        output.todos.append("I2C address not sourced from any datasheet chunk")
    if not spec.registers:
        output.todos.append("no register map sourced from datasheet-rag")
    _logger.info("driver_scaffolded", device=spec.device_name, registers=len(spec.registers))
    return output


def spec_from_chunks(
    device_name: str,
    compatible: str,
    kind: str,
    chunks: list[dict[str, str]],
) -> DriverSpec:
    """Build a DriverSpec from datasheet-rag chunks, extracting only sourced
    facts. Anything not found becomes an unresolved question, never a guess."""
    i2c_address: str | None = None
    registers: list[RegisterFact] = []
    unresolved: list[str] = []

    addr_pat = re.compile(r"(?i)i2c\s+address[^0-9a-fx]*(0x[0-9a-f]{2})")
    reg_pat = re.compile(r"(?i)\b([A-Z][A-Z0-9_]{2,})\b[^0-9a-fx]*(0x[0-9a-f]{2,4})")

    for chunk in chunks:
        text = chunk.get("text", "")
        provenance = f"{chunk.get('doc', '?')}/{chunk.get('section', '?')}"
        addr_match = addr_pat.search(text)
        if addr_match and i2c_address is None:
            i2c_address = addr_match.group(1)
        for name, address in reg_pat.findall(text):
            registers.append(
                RegisterFact(
                    name=name,
                    address=address,
                    description=f"from {provenance}",
                    provenance=provenance,
                )
            )
    if i2c_address is None:
        unresolved.append("I2C slave address (not found in provided chunks)")
    if not registers:
        unresolved.append("register map (no addresses found in provided chunks)")

    return DriverSpec(
        device_name=device_name,
        compatible=compatible,
        i2c_address=i2c_address,
        kind=kind,
        registers=tuple(registers),
        unresolved=tuple(unresolved),
    )
