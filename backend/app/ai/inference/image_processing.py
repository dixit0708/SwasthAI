import cv2
import numpy as np
from typing import Tuple

SUPPORTED_FORMATS = ["image/jpeg", "image/png", "image/jpg"]
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
# A highly-compressed image can decode into a much larger pixel buffer than
# its byte size suggests (e.g. a simple 20000x20000 PNG comfortably fits
# under 10MB on disk but decodes to ~1.2GB in memory). Cap decoded
# dimensions so a crafted upload can't balloon RSS before it ever reaches
# the resize step.
MAX_IMAGE_DIMENSION_PX = 6000

def validate_and_decode_image(contents: bytes, content_type: str) -> np.ndarray:
    """
    Validates file type and size, then decodes the image into an OpenCV numpy array in memory.
    Does NOT save the file to disk. Framework-agnostic.
    """
    # 1. Validate File Format
    if content_type not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported file format. Supported formats: {', '.join(SUPPORTED_FORMATS)}")

    # 2. Validate Empty Input
    if not contents:
        raise ValueError("File contents are empty.")

    # 3. Validate File Size
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")

    # 4. In-Memory Decode using OpenCV
    np_arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Failed to decode image or file is corrupted.")

    # 5. Validate Decoded Dimensions (after decode, before any resize/normalize)
    height, width = image.shape[:2]
    if height > MAX_IMAGE_DIMENSION_PX or width > MAX_IMAGE_DIMENSION_PX:
        raise ValueError(
            f"Image dimensions too large ({width}x{height}). "
            f"Maximum supported dimension is {MAX_IMAGE_DIMENSION_PX}px."
        )

    return image

def preprocess_for_cnn(image: np.ndarray, target_size: Tuple[int, int] = (224, 224)) -> np.ndarray:
    """
    Preprocesses the decoded image for CNN Inference.
    Resizes, normalizes, and expands dimensions.
    """
    # Resize
    resized_img = cv2.resize(image, target_size)
    
    # Convert BGR to RGB (OpenCV uses BGR by default, most ML models expect RGB)
    rgb_img = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
    
    # Normalize pixel values (0-1)
    normalized_img = rgb_img.astype(np.float32) / 255.0
    
    # Expand dims (batch size 1)
    batched_img = np.expand_dims(normalized_img, axis=0)
    
    return batched_img
