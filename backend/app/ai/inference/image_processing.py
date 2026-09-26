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
    
    # Convert to grayscale first (to remove color tints), then to 3-channel RGB
    # This matches the training pipeline's transforms.Grayscale(num_output_channels=3)
    gray_img = cv2.cvtColor(resized_img, cv2.COLOR_BGR2GRAY)
    rgb_img = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2RGB)
    
    # Normalize pixel values (0-1)
    normalized_img = rgb_img.astype(np.float32) / 255.0
    
    # Expand dims (batch size 1)
    batched_img = np.expand_dims(normalized_img, axis=0)
    
    return batched_img


def preprocess_for_skin(image: np.ndarray, target_size: Tuple[int, int] = (224, 224)) -> np.ndarray:
    """
    Preprocesses the decoded image for the Skin Disease CNN Inference.
    Resizes (aspect-preserving to 256), center crops (to 224), converts BGR to RGB,
    normalizes to [0, 1], and expands dims.
    """
    # 1. Convert BGR (OpenCV default) to RGB (what the PIL-trained model expects)
    rgb_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # 2. Aspect-preserving resize to 256 on the shortest edge
    h, w = rgb_img.shape[:2]
    if h < w:
        new_h, new_w = 256, int(w * (256 / h))
    else:
        new_h, new_w = int(h * (256 / w)), 256
    resized_img = cv2.resize(rgb_img, (new_w, new_h))
    
    # 3. Center Crop to target_size (e.g., 224x224)
    start_y = (new_h - target_size[1]) // 2
    start_x = (new_w - target_size[0]) // 2
    cropped_img = resized_img[start_y:start_y+target_size[1], start_x:start_x+target_size[0]]
    
    # 4. Normalize pixel values (0-1) - NO ImageNet normalization, exactly matching training
    normalized_img = cropped_img.astype(np.float32) / 255.0
    
    # 5. Expand dims (batch size 1)
    batched_img = np.expand_dims(normalized_img, axis=0)
    
    return batched_img
