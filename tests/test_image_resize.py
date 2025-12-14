import os
import importlib.util
import tempfile
from PIL import Image


def test_resize_reduces_large_image():
    # Create a large temporary image (2000x1500)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tmp_name = tmp.name
    tmp.close()

    try:
        img = Image.new("RGB", (2000, 1500), color=(255, 0, 0))
        img.save(tmp_name, format="JPEG")

        # Import claude_processor by file path so tests work when run from pytest
        base = os.getcwd()
        spec = importlib.util.spec_from_file_location(
            "claude_processor", os.path.join(base, "claude_processor.py")
        )
        cp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cp)  # type: ignore

        # Call the static resize method
        resized_path = cp.ClaudeProcessor.resize_image(tmp_name, max_dim=1000)
        assert os.path.exists(resized_path)

        # Verify dimensions are within bounds
        resized = Image.open(resized_path)
        w, h = resized.size
        assert max(w, h) <= 1000

    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        try:
            if 'resized_path' in locals() and os.path.exists(resized_path):
                os.unlink(resized_path)
        except OSError:
            pass
