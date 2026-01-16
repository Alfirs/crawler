from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ImageProcessingSettings(BaseSettings):
    """Low-level parameters controlling OpenCV wheel detection."""

    max_image_size: int = Field(
        1600,
        description="Maximum size (longest edge) for input images to speed up processing.",
    )
    gaussian_kernel: int = Field(9, description="Odd kernel size for Gaussian blur.")
    canny_threshold1: int = Field(50, description="Lower hysteresis threshold for Canny.")
    canny_threshold2: int = Field(150, description="Upper hysteresis threshold for Canny.")
    hough_dp: float = Field(1.2, description="Inverse ratio of accumulator resolution for HoughCircles.")
    hough_min_dist_ratio: float = Field(
        0.25,
        description="Minimum distance between circle centers expressed as a ratio of image width.",
    )
    hough_param1: int = Field(100, description="Higher Canny threshold for HoughCircles.")
    hough_param2: int = Field(40, description="Accumulator threshold for HoughCircles.")
    hough_min_radius_ratio: float = Field(
        0.07, description="Minimum radius ratio relative to the smallest image dimension."
    )
    hough_max_radius_ratio: float = Field(
        0.22, description="Maximum radius ratio relative to the smallest image dimension."
    )
    wheel_region_height_ratio: float = Field(
        0.5, description="Consider only the lower portion of the image for wheel detection."
    )
    mask_padding_ratio: float = Field(
        0.12, description="Extra relative padding applied to the detected wheel radius for masks."
    )
    overlay_radius_scale: float = Field(
        0.8, description="Scale factor for final overlay diameter relative to detected radius."
    )


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    kie_api_key: str = Field(..., alias="KIE_API_KEY")
    kie_base_url: str = Field("https://api.kie.ai/api/v1", alias="KIE_BASE_URL")
    seedream_model_name: str = Field("nano-banana-pro", alias="SEEDREAM_MODEL_NAME")
    seedream_render_model_name: Optional[str] = None
    render_aspect_ratio: str = Field("16:9", alias="RENDER_ASPECT_RATIO")
    render_resolution: str = Field("2K", alias="RENDER_RESOLUTION")
    render_output_format: str = Field("jpg", alias="RENDER_OUTPUT_FORMAT")
    base_media_dir: Path = Field(Path("./media"), alias="BASE_MEDIA_DIR")
    kie_timeout_seconds: int = Field(120, description="Timeout for kie.ai HTTP requests.")
    kie_poll_interval: float = Field(3.0, description="Seconds between polling task status.")
    kie_poll_timeout: int = Field(180, description="Maximum seconds to wait for task completion.")
    kie_upload_mode: Literal["kie", "fileio"] = Field("kie", description="Preferred method for preparing image URLs.")
    kie_upload_base_url: str = Field("https://kieai.redpandaai.co", alias="KIE_UPLOAD_BASE_URL")
    kie_upload_path: str = Field("wheel-swap", alias="KIE_UPLOAD_PATH")
    environment: Literal["local", "dev", "prod"] = Field("local")
    use_local_overlay_only: bool = Field(
        False,
        description=(
            "If true, skip nano-banana-pro edit and always use local wheel overlay for swaps (debug only). "
            "Keep this false in production so the bot returns model results."
        ),
    )

    image_processing: ImageProcessingSettings = Field(default_factory=ImageProcessingSettings)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    settings = Settings()
    base_dir = settings.base_media_dir
    # Ensure base media directories exist early
    for subdir in ("originals", "masks", "results", "temp"):
        (base_dir / subdir).mkdir(parents=True, exist_ok=True)
    return settings


def resolve_media_path(*paths: str | Path, create_parents: bool = False) -> Path:
    """Helper for building paths inside BASE_MEDIA_DIR."""

    settings = get_settings()
    resolved = settings.base_media_dir.joinpath(*paths)
    if create_parents:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved
