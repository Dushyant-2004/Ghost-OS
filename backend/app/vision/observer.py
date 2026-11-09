from pathlib import Path

from app.core.config import Settings


class VisionUnavailable(RuntimeError):
    pass


def unavailable_observation(screenshot_path: Path, page_url: str, page_title: str) -> dict:
    return {
        "page_url": page_url,
        "page_title": page_title,
        "screenshot_path": str(screenshot_path),
        "visible_elements": [],
        "detected_dialogs": [],
        "page_state": "unavailable",
        "observation_summary": "Vision analysis was not performed because no vision provider is configured.",
        "confidence": 0.0,
    }


def validate_vision_configuration(settings: Settings) -> None:
    if not settings.vision_configured:
        raise VisionUnavailable("Vision analysis is unavailable: configure VISION_PROVIDER and OPENAI_API_KEY.")
