"""scope_lock: UserPromptSubmit hook enforcing the domain lock (section 10).

Deterministic and deliberately conservative: any domain vocabulary allows the
prompt, and a block requires both zero domain signal and a match against a
narrow out-of-scope pattern list. Ambiguous prompts pass through; LLM-backed
classification for those arrives with the intake classifier (section 3).
"""

import re
from typing import cast

from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    SyncHookJSONOutput,
    UserPromptSubmitHookInput,
)

REFUSAL = (
    "deepgent handles AV, CV, embedded, and robotics-adjacent edge AI "
    "engineering tasks only; this request is out of scope."
)

# Single lowercase words matched against the prompt's word set. Deliberately
# excludes short ambiguous tokens (av, cv, pi, can) that would false-positive
# as substrings of ordinary English.
_DOMAIN_WORDS = frozenset(
    {
        "jetson",
        "orin",
        "xavier",
        "tegra",
        "tegrastats",
        "l4t",
        "jetpack",
        "nvidia",
        "cuda",
        "cudnn",
        "tensorrt",
        "trt",
        "trtexec",
        "deepstream",
        "gstreamer",
        "nvcc",
        "ros",
        "ros2",
        "nav2",
        "moveit",
        "gazebo",
        "carla",
        "rviz",
        "colcon",
        "canbus",
        "socketcan",
        "candump",
        "gmsl",
        "gmsl2",
        "serdes",
        "csi",
        "mipi",
        "camera",
        "lidar",
        "radar",
        "imu",
        "gnss",
        "ultrasonic",
        "sensor",
        "sensors",
        "fusion",
        "calibration",
        "slam",
        "odometry",
        "perception",
        "detection",
        "detector",
        "segmentation",
        "tracking",
        "yolo",
        "onnx",
        "quantize",
        "quantized",
        "quantization",
        "int8",
        "fp16",
        "inference",
        "model",
        "training",
        "dataset",
        "latency",
        "throughput",
        "fps",
        "thermal",
        "embedded",
        "firmware",
        "mcu",
        "rtos",
        "freertos",
        "zephyr",
        "stm32",
        "esp32",
        "arduino",
        "raspberry",
        "hailo",
        "gpio",
        "i2c",
        "spi",
        "uart",
        "pwm",
        "adc",
        "kernel",
        "driver",
        "drivers",
        "devicetree",
        "bootloader",
        "aarch64",
        "arm64",
        "toolchain",
        "compile",
        "compiler",
        "container",
        "docker",
        "board",
        "boards",
        "flash",
        "autonomous",
        "vehicle",
        "robot",
        "robotics",
        "drone",
        "uav",
        "opencv",
        "npu",
        "accelerator",
        "misra",
        "golden",
        "goldens",
        "benchmark",
        "profiling",
    }
)

# Multi-word domain phrases checked as substrings of the lowercased prompt.
_DOMAIN_PHRASES = (
    "device tree",
    "cross compile",
    "cross-compile",
    "can bus",
    "edge ai",
    "computer vision",
    "point cloud",
)

_OUT_OF_SCOPE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b(poem|poetry|sonnet|essay|novel|short story|song|lyrics)\b",
        r"\b(recipe|cooking|baking)\b",
        r"\b(horoscope|astrology|tarot)\b",
        r"\b(medical|legal|financial|investment|relationship|dating) advice\b",
        r"\b(homework|book report|cover letter|resume|cv review)\b",
        r"\bmarketing (copy|email|campaign)\b",
        r"\b(joke|riddle|trivia)\b",
    )
)


def is_in_scope(prompt: str) -> bool:
    """Deterministic scope check; True unless clearly out of domain."""
    lowered = prompt.lower()
    words = set(re.findall(r"[a-z0-9_+-]+", lowered))
    if words & _DOMAIN_WORDS:
        return True
    if any(phrase in lowered for phrase in _DOMAIN_PHRASES):
        return True
    return not any(pattern.search(lowered) for pattern in _OUT_OF_SCOPE_PATTERNS)


async def scope_lock(
    input_data: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> SyncHookJSONOutput:
    """Refuse out-of-domain prompts with one line (section 10)."""
    data = cast(UserPromptSubmitHookInput, input_data)
    if is_in_scope(data["prompt"]):
        return {}
    return {"decision": "block", "reason": REFUSAL}
