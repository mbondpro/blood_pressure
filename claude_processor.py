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

    def create_image_message(
        self, image: str, prompt: str, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """Build a message block list containing an image and a text prompt.

        The image is read from disk, base64-encoded, and returned alongside a
        text block containing `prompt` in a list suitable for inclusion in the
        conversation `messages` list.

        Args:
            image: Path to the image file to include.
            prompt: The textual prompt/question associated with the image.
            use_cache: If True, add cache_control to the image block to enable
                Anthropic's prompt caching feature (reduces token usage for
                repeated requests with the same image).

        Returns:
            A list of dict blocks representing an image block and a text block.

        Raises:
            ValueError: If the `image` file cannot be found.
        """

        try:
            logger.debug("Encoding image for Claude: %s", image)
            with open(image, "rb") as f:
                image_bytes = base64.b64encode(f.read()).decode("utf-8")
        except FileNotFoundError as exc:
            logger.debug("Image file not found when encoding: %s", image)
            raise ValueError(f"Image file not found: {image}") from exc

        image_block: Dict[str, Any] = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": self.image_type_from_filename(image),
                "data": image_bytes,
            },
        }

        # Add cache control to enable prompt caching on Anthropic's servers
        # Only include cache_control if the current conversation doesn't
        # already contain too many such blocks (Anthropic limits to 4).
        if use_cache:
            # Count existing blocks with cache_control in current messages
            existing_cache_blocks = 0
            for m in getattr(self, "messages", []) or []:
                content = m.get("content") if isinstance(m, dict) else None
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and "cache_control" in blk:
                            existing_cache_blocks += 1

            if existing_cache_blocks < 4:
                image_block["cache_control"] = {"type": "ephemeral"}
            else:
                logger.debug(
                    "Skipping cache_control for image %s; existing cache blocks=%d",
                    image,
                    existing_cache_blocks,
                )

        return [
            image_block,
            # Text Block
            {"type": "text", "text": prompt},
        ]

    def process_bp_image(
        self, image_path: str, use_cache: bool = True, skip_resize: bool = False
    ) -> Dict[str, Any]:
        """Extract blood pressure data from an image of a BP monitor.

        Uses Claude's vision API to analyze an image containing blood pressure
        monitor output and extract the systolic, diastolic, pulse, and
        optionally timestamp values in structured JSON format.

        Args:
            image_path: Path to the image file containing BP monitor reading.
            use_cache: If True, enable Anthropic's prompt caching to reduce
                token usage for repeated requests with the same image.

        Returns:
            Dictionary with keys: 'systolic', 'diastolic', 'pulse', and
            optionally 'timestamp'. All numeric values are integers.

        Raises:
            ValueError: If the image cannot be read or parsed.
            OSError: If there's an issue accessing the file.
        """
        if not os.path.exists(image_path):
            raise ValueError(f"Image file does not exist: {image_path}")

        # Resize/convert image if requested to reduce upload size and prepare
        # a negated grayscale image for better OCR. If `skip_resize` is True
        # the caller has already prepared the image and we should not modify it.
        resized_path = image_path
        try:
            if not skip_resize:
                resized_path = self.resize_image(image_path, max_dim=1000)
        except (OSError, ValueError):  # If resizing fails, continue with original image
            logger.debug("Image resize failed, continuing with original file", exc_info=True)

        prompt = """Analyze this blood pressure monitor display image carefully.
    The numbers appear on a digital display (light text on a darker background).
    If the image is compressed or slightly unclear, do your best to read the values accurately.

    Extract the following integer values only (no units):
    - systolic: the systolic blood pressure (top number), usually left of "SYS" or labeled "SYS".
    - diastolic: the diastolic blood pressure (bottom number), usually left of "DIA" or labeled "DIA".
    - pulse: the heart rate/pulse, usually near or labeled "PUL".

    Return ONLY a single JSON code block (use ```json ... ```). The JSON must be either the older format:
    {"systolic": 120, "diastolic": 80, "pulse": 72}
    or the newer format with a comment and data object and an optional explanation string:
    {"comment": "Some text", "explanation": "I saw '120' to the left of 'SYS'...", "data": {"systolic": 120, "diastolic": 80, "pulse": 72}}

    Include an `explanation` string (short, human-readable) describing where each value was read from on the image (for example: which characters or labels you saw). If you are unsure of a value, return null for that field.

    If you include any explanation text outside the JSON block, place it after the code block. The application will display that explanation to the user.

    All numeric fields must be integers. Do not include any extra text before the code block. If you cannot read numbers at all, return JSON with all fields set to null and include an explanation.
    """

        # Use a fresh message list for this request to avoid accumulating
        # image blocks (and cache_control) across multiple calls.
        old_messages = list(self.messages)
        try:
            self.messages = []
            self.add_user_message(
                self.create_image_message(resized_path, prompt, use_cache=use_cache)
            )
            response = self.chat()
            text_response = self.text_from_message(response)
        finally:
            # restore prior conversation messages
            try:
                self.messages = old_messages
            except Exception:
                self.messages = []
            # clean up any temporary resized file we created (but not if the
            # caller passed in a preprocessed image via `skip_resize`).
            try:
                if not skip_resize and resized_path != image_path and os.path.exists(resized_path):
                    os.unlink(resized_path)
            except OSError:
                logger.debug("Failed to remove temporary resized image %s", resized_path, exc_info=True)

        # Parse JSON from response, with fallback extraction via regex
        try:
            # Try to extract JSON from the response
            # Claude might wrap it in markdown code blocks
            # Extract the first code block (prefer explicit ```json). Keep any
            # text outside the code block as a potential human explanation.
            json_str = None
            outside_text = ""
            if "```json" in text_response:
                head, tail = text_response.split("```json", 1)
                if "```" in tail:
                    json_str, rest = tail.split("```", 1)
                    outside_text = (head + rest).strip()
                else:
                    json_str = tail.strip()
            elif "```" in text_response:
                head, tail = text_response.split("```", 1)
                if "```" in tail:
                    json_str, rest = tail.split("```", 1)
                    outside_text = (head + rest).strip()
                else:
                    json_str = tail.strip()
            else:
                json_str = text_response.strip()

            data = json.loads(json_str)

            # Handle new format with "comment" and "data" keys
            if "data" in data and isinstance(data["data"], dict):
                bp_values = data["data"]
                result = {
                    "systolic": bp_values.get("systolic"),
                    "diastolic": bp_values.get("diastolic"),
                    "pulse": bp_values.get("pulse"),
                }
                if "comment" in data:
                    result["comment"] = data["comment"]
                if "explanation" in data:
                    result["explanation"] = data["explanation"]
            else:
                result = data

            # If any required numeric field is missing or not an int/null,
            # attempt a regex-based extraction from the raw text as a fallback.
            def _as_int_or_none(v):
                try:
                    if v is None:
                        return None
                    return int(v)
                except Exception:
                    return None

            for k in ["systolic", "diastolic", "pulse"]:
                result[k] = _as_int_or_none(result.get(k))

            if not all(k in result and (isinstance(result[k], int) or result[k] is None) for k in ["systolic", "diastolic", "pulse"]):
                # Fallback: try to extract labeled values from the plain text
                import re

                text = text_response
                found = {}
                patterns = {
                    "systolic": r"SYS[:\s]*([0-9]{2,3})",
                    "diastolic": r"DIA[:\s]*([0-9]{2,3})",
                    "pulse": r"PUL[:\s]*([0-9]{2,3})",
                }
                for key, pat in patterns.items():
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        found[key] = int(m.group(1))

                # Generic three-number sequence fallback (systolic, diastolic, pulse)
                if len(found) < 3:
                    nums = re.findall(r"\b([0-9]{2,3})\b", text)
                    if len(nums) >= 3:
                        try:
                            found.setdefault("systolic", int(nums[0]))
                            found.setdefault("diastolic", int(nums[1]))
                            found.setdefault("pulse", int(nums[2]))
                        except Exception:
                            pass

                # Merge found values into result when missing
                for k, v in found.items():
                    if result.get(k) is None:
                        result[k] = v

            # If we have any outside-text explanation, set it on the result if
            # an explicit explanation field wasn't provided.
            if outside_text and not result.get("explanation"):
                # Keep outside_text reasonably short
                result["explanation"] = outside_text[:1000]

            # Final validation: ensure keys exist
            if not all(k in result for k in ["systolic", "diastolic", "pulse"]):
                raise ValueError("Missing required fields in JSON response after fallback attempts")

            return result
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            raise ValueError(f"Failed to parse JSON from response: {e}") from e

    @staticmethod
    # Tests and usage make this function utility-like; allow a few locals here.
    # pylint: disable=too-many-locals
    def resize_image(image_path: str, max_dim: int = 1000, negate: bool = True) -> str:
        """Resize an image so its largest dimension is no greater than `max_dim`.

        If the image is already within bounds, returns the original path (unless
        negate is True, in which case a processed copy is created).
        Otherwise writes a resized copy to a temporary file and returns its path.

        Args:
            image_path: Path to the image file to resize.
            max_dim: Maximum dimension (width or height) for the output image.
            negate: If True, convert image to grayscale and negate colors.

        Returns:
            Path to the resized (and optionally negated) image.
        """
        if not os.path.exists(image_path):
            raise ValueError(f"Image file does not exist: {image_path}")

        try:
            img = Image.open(image_path)
        except OSError as exc:
            raise ValueError(f"Unable to open image: {image_path}") from exc

        # Convert to grayscale if negate is True
        if negate:
            img = img.convert("L")

        width, height = img.size
        max_current = max(width, height)

        # Skip resizing for images already smaller than 1500px to preserve detail
        if max_current <= 1500 or max_current <= max_dim:
            # If negate is True but image is already within size bounds,
            # still need to save the negated version
            if negate:
                from PIL import ImageOps
                img = ImageOps.invert(img)
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
                    if fmt == "PNG":
                        img.save(tmp_name, format="PNG")
                    else:
                        img.save(tmp_name, format=fmt, quality=95, optimize=True)
                except OSError:
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
                    raise
                return tmp_name
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

        # Negate the image if requested
        if negate:
            from PIL import ImageOps
            resized = ImageOps.invert(resized)

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
            # Save with quality settings optimized for readability
            if fmt == "PNG":
                # PNG is lossless; preserve maximum detail for text readability
                resized.save(tmp_name, format="PNG")
            else:
                # JPEG: use high quality to minimize compression artifacts on text/numbers
                resized.save(tmp_name, format=fmt, quality=95, optimize=True)
        except OSError:
            # cleanup on failure
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        return tmp_name
