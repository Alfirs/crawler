class ImageClient:
    """Service responsible for generating cover images."""

    def __init__(self) -> None:
        # TODO: accept API endpoint and credentials
        ...

    def generate_image(self, image_prompt: str) -> str:
        """Generate image and return a URL to it.

        This stub simply returns a fake CDN link.
        """

        safe_prompt = image_prompt.replace(" ", "-")[:64]
        return f"https://img.local/{safe_prompt or 'cover'}.png"
