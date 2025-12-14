"""Utilities for interacting with Anthropic Claude models.

This module provides the `ClaudeProcessor` class which encapsulates an
Anthropic client and helper methods for building conversations, encoding
images as base64 message blocks, and sending chat requests to a Claude
model. It also contains small utility functions for extracting text from
message objects and resolving image MIME types from filenames.
"""

import os
import logging
import base64
import json
import tempfile
from typing import Any, Dict, List

from dotenv import load_dotenv
from anthropic import Anthropic
from anthropic.types import Message
from PIL import Image

load_dotenv()

logger = logging.getLogger(__name__)

TEMPERATURE = float(os.getenv("CLAUDE_TEMPERATURE", "0.0"))
THINKING_BUDGET = int(os.getenv("CLAUDE_THINKING_BUDGET", "1024"))
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


class ClaudeProcessor:
    """Processor for interacting with the Claude API."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 1.0,
        thinking_budget: int = 1024,
        api_key: str | None = None,
    ):
        """Initialize the `ClaudeProcessor`.

        Args:
            model: Optional model name to use for the Anthropic client. If not
                provided, a default model string is used.
            temperature: Default sampling temperature for chat requests.
            thinking_budget: Default token budget to use when Anthropic
                "thinking" mode is enabled.

        The Anthropic client is created and stored on the instance along with
        an empty messages list used to build conversations. The provided
        `temperature` and `thinking_budget` are stored on the instance and
        used by `chat()`.
        """

        # Resolve API key from argument or environment. Support a few common
        # environment variable names so the key can be provided in containers
        # or CI without changing code.
        api_key = (
            api_key
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("CLAUDE_API_KEY")
            or os.getenv("ANTHROPIC_AUTH_TOKEN")
        )

        if not api_key:
            raise RuntimeError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY or CLAUDE_API_KEY in the environment."
            )

        self.client = Anthropic(api_key=api_key)
        self.model = model or CLAUDE_MODEL
        self.messages: List[Dict[str, Any]] = []
        self.temperature = temperature
        self.thinking_budget = thinking_budget

    def add_user_message(self, message: Any) -> None:
        """Append a user message to a message list.

        Args:
            message: Either an `anthropic.types.Message` instance or a raw
                string/object representing the message content. If `message` is
                a `Message`, its `.content` field is used; otherwise the value
                is used directly.
        """

        user_message = {
            "role": "user",
            "content": message.content if isinstance(message, Message) else message,
        }

        self.messages.append(user_message)

    def add_assistant_message(self, message: Any) -> None:
        """Append an assistant message to a message list.

        Args:
            message: Either an `anthropic.types.Message` instance or a raw
                string/object representing the message content. If `message` is
                a `Message`, its `.content` field is used; otherwise the value
                is used directly.
        """

        assistant_message = {
            "role": "assistant",
            "content": message.content if isinstance(message, Message) else message,
        }

        self.messages.append(assistant_message)

    def chat(
        self,
        system: str | None = None,
        stop_sequences: List[str] | None = None,
        tools: List[Dict[str, Any]] | None = None,
        thinking: bool = False,
    ) -> Message:
        """Send a chat request to the Anthropic API and return the response.

        Uses the instance's `self.messages` as the conversation and reads
        `temperature` and `thinking_budget` from the corresponding instance
        attributes.

        Args:
            system: Optional system prompt string.
            stop_sequences: List of sequences that will stop generation.
            tools: Optional tools to include in the request payload.
            thinking: Enable Anthropic "thinking" mode when True.

        Returns:
            The raw response object returned by `self.client.messages.create`.
        """

        params = {
            "model": self.model,
            "max_tokens": 4000,
            "messages": self.messages,
            "temperature": self.temperature,
            "stop_sequences": stop_sequences or [],
        }

        if thinking:
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }

        if tools:
            params["tools"] = tools

        if system:
            params["system"] = system

        message = self.client.messages.create(**params)
        return message

    def text_from_message(self, message) -> str:
        """Extract and concatenate text blocks from a message object.

        Args:
            message: An object whose `content` attribute is an iterable of
                blocks, where text blocks have `.type == "text"` and a
                `.text` attribute.

        Returns:
            A single string containing the joined text from all text blocks,
            separated by newlines.
        """

        return "\n".join(
            [block.text for block in message.content if block.type == "text"]
        )

    def image_type_from_filename(self, filename: str) -> str:
        """Return the MIME type for an image filename.

        Args:
            filename: The path or filename of the image.

        Returns:
            A MIME type string such as "image/png" or "image/jpeg".

        Raises:
            ValueError: If the file extension is not a supported image type.
        """

        ext = os.path.splitext(filename)[1].lower()

        if ext == ".png":
            return "image/png"
        if ext in [".jpg", ".jpeg"]:
            return "image/jpeg"
        if ext == ".gif":
            return "image/gif"
        raise ValueError(f"Unsupported image extension: {ext}")

    def create_image_message(self, image: str, prompt: str) -> List[Dict[str, Any]]:
        """Build a message block list containing an image and a text prompt.

        The image is read from disk, base64-encoded, and returned alongside a
        text block containing `prompt` in a list suitable for inclusion in the
        conversation `messages` list.

        Args:
            image: Path to the image file to include.
            prompt: The textual prompt/question associated with the image.

        Returns:
            A list of dict blocks representing an image block and a text block.

        Raises:
            ValueError: If the `image` file cannot be found.
        """

        try:
            with open(image, "rb") as f:
                image_bytes = base64.b64encode(f.read()).decode("utf-8")
        except FileNotFoundError as exc:
            raise ValueError(f"Image file not found: {image}") from exc

        return [
            # Image Block
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": self.image_type_from_filename(image),
                    "data": image_bytes,
                },
            },
            # Text Block
            {"type": "text", "text": prompt},
        ]

    def process_bp_image(self, image_path: str) -> Dict[str, Any]:
        """Extract blood pressure data from an image of a BP monitor.

        Uses Claude's vision API to analyze an image containing blood pressure
        monitor output and extract the systolic, diastolic, pulse, and
        optionally timestamp values in structured JSON format.

        Args:
            image_path: Path to the image file containing BP monitor reading.

        Returns:
            Dictionary with keys: 'systolic', 'diastolic', 'pulse', and
            optionally 'timestamp'. All numeric values are integers.

        Raises:
            ValueError: If the image cannot be read or parsed.
            OSError: If there's an issue accessing the file.
        """
        if not os.path.exists(image_path):
            raise ValueError(f"Image file does not exist: {image_path}")

        # Resize image if it's larger than allowed dimensions to reduce upload size
        resized_path = image_path
        try:
            resized_path = self.resize_image(image_path, max_dim=1000)
        except (OSError, ValueError):  # If resizing fails, continue with original image
            logger.debug("Image resize failed, continuing with original file", exc_info=True)

        prompt = """Analyze this image of a blood pressure monitor display.
Extract the following values and return them in valid JSON format:
- systolic: the systolic blood pressure (top number)
- diastolic: the diastolic blood pressure (bottom number)
- pulse: the heart rate/pulse

Return ONLY valid JSON with these fields. Example:
{"systolic": 120, "diastolic": 80, "pulse": 72}
"""

        try:
            self.add_user_message(self.create_image_message(resized_path, prompt))
            response = self.chat()
            text_response = self.text_from_message(response)
        finally:
            # clean up any temporary resized file
            try:
                if resized_path != image_path and os.path.exists(resized_path):
                    os.unlink(resized_path)
            except OSError:
                logger.debug("Failed to remove temporary resized image %s", resized_path, exc_info=True)

        # Parse JSON from response
        try:
            # Try to extract JSON from the response
            # Claude might wrap it in markdown code blocks
            if "```json" in text_response:
                json_str = text_response.split("```json")[1].split("```")[0].strip()
            elif "```" in text_response:
                json_str = text_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = text_response.strip()

            data = json.loads(json_str)

            # Validate required fields
            if not all(k in data for k in ["systolic", "diastolic", "pulse"]):
                raise ValueError("Missing required fields in JSON response")

            return data
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            raise ValueError(f"Failed to parse JSON from response: {e}") from e

    @staticmethod
    # Tests and usage make this function utility-like; allow a few locals here.
    # pylint: disable=too-many-locals
    def resize_image(image_path: str, max_dim: int = 1000) -> str:
        """Resize an image so its largest dimension is no greater than `max_dim`.

        If the image is already within bounds, returns the original path.
        Otherwise writes a resized copy to a temporary file and returns its path.
        """
        if not os.path.exists(image_path):
            raise ValueError(f"Image file does not exist: {image_path}")

        try:
            img = Image.open(image_path)
        except OSError as exc:
            raise ValueError(f"Unable to open image: {image_path}") from exc

        width, height = img.size
        max_current = max(width, height)
        if max_current <= max_dim:
            return image_path

        ratio = float(max_dim) / float(max_current)
        new_size = (int(width * ratio), int(height * ratio))

        # Choose a resampling filter compatible across Pillow versions
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            # Use getattr to avoid static attribute checks on PIL versions
            resample = getattr(Image, "LANCZOS", getattr(Image, "BICUBIC", 3))

        resized = img.resize(new_size, resample)

        ext = os.path.splitext(image_path)[1].lower()
        fmt = {
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".png": "PNG",
            ".gif": "GIF",
        }.get(ext, "JPEG")

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp_name = tmp.name

        try:
            # Save with reasonable quality settings for JPEG
            save_kwargs: Dict[str, Any] = {"format": fmt}
            if fmt == "JPEG":
                save_kwargs["quality"] = 85
                save_kwargs["optimize"] = True
            resized.save(tmp_name, **save_kwargs)
        except OSError:
            # cleanup on failure
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        return tmp_name
