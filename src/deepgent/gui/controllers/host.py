"""Host/dashboard controller: detection, diagnostics, and setup. Qt-free."""

from pathlib import Path

from deepgent.boards import register_local_target
from deepgent.host import HostProfile, apply_config, derive_config, detect_host
from deepgent.host.diagnostics import Check, run_checks


class HostController:
    """Adapts host detection, diagnostics, and setup for the GUI."""

    def detect(self) -> HostProfile:
        return detect_host()

    def checks(self, profile: HostProfile | None = None) -> list[Check]:
        return run_checks(profile)

    def setup(self, force: bool = False) -> tuple[str, bool, bool]:
        """Detect, write config, and register the local target.

        Returns (config_path, written, registered_local).
        """
        profile = detect_host()
        config = derive_config(profile)
        path, written = apply_config(profile, force=force)
        registered = False
        if config.local_execution:
            register_local_target(profile.device_class, list(config.capabilities), profile.os)
            registered = True
        return str(path), written, registered

    def config_path(self) -> Path:
        return Path.home() / ".deepgent" / "config.toml"
