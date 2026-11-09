import asyncio
from pathlib import Path
from typing import Any

from app.core.config import Settings


class DesktopSafetyError(RuntimeError):
    pass


class DesktopController:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = False
        self.stopped = False
        self.action_count = 0

    def _require_enabled(self) -> None:
        if not self.enabled or self.stopped:
            raise DesktopSafetyError("Desktop automation is disabled or stopped.")
        if self.action_count >= self.settings.desktop_max_actions:
            raise DesktopSafetyError("Desktop action limit reached.")

    def enable(self) -> dict[str, Any]:
        if not self.settings.desktop_automation_enabled:
            raise DesktopSafetyError("Desktop automation is disabled by configuration.")
        if not self.settings.vision_configured:
            raise DesktopSafetyError("Desktop automation requires a configured vision provider.")
        self.enabled = True
        self.stopped = False
        self.action_count = 0
        return self.status()

    def stop(self) -> dict[str, Any]:
        self.stopped = True
        self.enabled = False
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "stopped": self.stopped,
            "action_count": self.action_count,
            "max_actions": self.settings.desktop_max_actions,
        }

    async def screenshot(self) -> dict[str, Any]:
        self._require_enabled()
        try:
            import pyautogui
        except ImportError as error:
            raise DesktopSafetyError("PyAutoGUI is not installed for desktop capture.") from error
        output = Path(self.settings.ghostos_workspace).resolve() / "screenshots" / "desktop.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(pyautogui.screenshot, str(output))
        return {"path": str(output), "status": "captured"}

    async def action(self, name: str, **kwargs: Any) -> dict[str, Any]:
        self._require_enabled()
        allowed = {"move_mouse", "click", "double_click", "scroll", "type_text", "press_key", "hotkey"}
        if name not in allowed:
            raise DesktopSafetyError(f"Desktop action is not allowlisted: {name}")
        if name in {"press_key", "hotkey"} and any(
            key.lower() in {"alt", "delete", "win", "ctrl+alt+delete"} for key in kwargs.get("keys", [])
        ):
            raise DesktopSafetyError("Destructive or system-level shortcuts are blocked.")
        try:
            import pyautogui
        except ImportError as error:
            raise DesktopSafetyError("PyAutoGUI is not installed for desktop actions.") from error
        width, height = pyautogui.size()
        if name in {"move_mouse", "click", "double_click"}:
            x, y = int(kwargs.get("x", -1)), int(kwargs.get("y", -1))
            if not (0 <= x < width and 0 <= y < height):
                raise DesktopSafetyError("Screen coordinates are outside the visible screen.")
        operation_names = {
            "move_mouse": "moveTo",
            "double_click": "doubleClick",
            "type_text": "write",
            "press_key": "press",
        }
        operation = getattr(pyautogui, operation_names.get(name, name))
        if name == "hotkey":
            await asyncio.to_thread(operation, *kwargs.get("keys", []))
        else:
            await asyncio.to_thread(operation, **kwargs)
        self.action_count += 1
        return {"action": name, "status": "completed", "action_count": self.action_count}
