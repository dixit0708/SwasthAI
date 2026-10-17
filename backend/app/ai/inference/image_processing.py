import os
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


def apply_color_constancy(image: np.ndarray) -> np.ndarray:
    """
    Applies Gray-World Color Constancy to normalize ambient lighting and camera white balance.
    Expects BGR image as input from OpenCV.
    """
    img_f = image.astype(np.float32)
    mean_b = np.mean(img_f[:, :, 0])
    mean_g = np.mean(img_f[:, :, 1])
    mean_r = np.mean(img_f[:, :, 2])
    
    if mean_b == 0 or mean_g == 0 or mean_r == 0:
        return image
        
    gray_val = (mean_b + mean_g + mean_r) / 3.0
    
    img_f[:, :, 0] = np.clip(img_f[:, :, 0] * (gray_val / mean_b), 0, 255)
    img_f[:, :, 1] = np.clip(img_f[:, :, 1] * (gray_val / mean_g), 0, 255)
    img_f[:, :, 2] = np.clip(img_f[:, :, 2] * (gray_val / mean_r), 0, 255)
    
    return img_f.astype(np.uint8)

def find_lesion_roi(rgb_img: np.ndarray) -> Tuple[int, int, int, int]:
    """
    Detects the spatial bounding box (ROI) of skin lesions using color-contrast saliency in LAB space.
    Accurately localizes off-center lesions, asymmetrical plaques, and focal rashes.
    """
    h, w = rgb_img.shape[:2]
    lab = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2LAB)
    a = lab[:, :, 1].astype(float)
    b = lab[:, :, 2].astype(float)
    
    med_a, std_a = np.median(a), np.std(a)
    med_b, std_b = np.median(b), np.std(b)
    
    # Distance from median healthy skin tone in color space
    dist = np.sqrt(((a - med_a) / (std_a + 1e-5)) ** 2 + ((b - med_b) / (std_b + 1e-5)) ** 2)
    mask = (dist > 1.2).astype(np.uint8) * 255
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        valid = [c for c in contours if cv2.contourArea(c) > 0.005 * (h * w)]
        if valid:
            all_pts = np.concatenate(valid)
            x, y, cw, ch = cv2.boundingRect(all_pts)
            # Add 15% margin around the detected lesion
            pad_x = int(cw * 0.15)
            pad_y = int(ch * 0.15)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + cw + pad_x)
            y2 = min(h, y + ch + pad_y)
            if (x2 - x1) >= 40 and (y2 - y1) >= 40:
                return x1, y1, x2, y2
                
    # Fallback default center box
    return int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8)


def preprocess_for_skin(image: np.ndarray, target_size: Tuple[int, int] = (224, 224)) -> np.ndarray:
    """
    Preprocesses the decoded image for Skin Disease CNN Inference using a universal multi-scale spatial pyramid.
    - Global Scale (1.0x): captures wide-field and facial distributions (e.g. acne, extensive rashes, alopecia)
    - Center Scale (0.55x): captures centered focal lesions (e.g. hives wheals, nail beds)
    - Saliency ROI Scale: dynamically extracts off-center or asymmetrical lesions across the skin
    - Macro Scale (0.35x): resolves fine dermatoscopic surface textures (e.g. scaling, follicular plugs)
    - Tight crop fallback (<200px): uses exact user framing without secondary cropping
    Returns batched array of shape (N, H, W, C).
    """
    # 1. Convert BGR (OpenCV default) to RGB (what the CNN expects)
    rgb_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w = rgb_img.shape[:2]
    
    crops = []
    
    # Scale 0: Global Full View (1.0x)
    r_full = cv2.resize(rgb_img, target_size, interpolation=cv2.INTER_AREA)
    crops.append(r_full.astype(np.float32) / 255.0)
    
    if min(h, w) >= 200:
        # Scale 1: Geometric Center Crop (0.55x)
        ch, cw = int(h * 0.55), int(w * 0.55)
        c_center = rgb_img[(h - ch) // 2:(h + ch) // 2, (w - cw) // 2:(w + cw) // 2]
        r_center = cv2.resize(c_center, target_size, interpolation=cv2.INTER_AREA)
        crops.append(r_center.astype(np.float32) / 255.0)
        
        # Scale 2: Saliency-Guided Lesion ROI Crop (adaptive to off-center lesions)
        x1, y1, x2, y2 = find_lesion_roi(rgb_img)
        c_roi = rgb_img[y1:y2, x1:x2]
        r_roi = cv2.resize(c_roi, target_size, interpolation=cv2.INTER_AREA)
        crops.append(r_roi.astype(np.float32) / 255.0)
        
        # Scale 3: Macro Close-up Crop (0.35x)
        ch3, cw3 = int(h * 0.35), int(w * 0.35)
        c_macro = rgb_img[(h - ch3) // 2:(h + ch3) // 2, (w - cw3) // 2:(w + cw3) // 2]
        r_macro = cv2.resize(c_macro, target_size, interpolation=cv2.INTER_AREA)
        crops.append(r_macro.astype(np.float32) / 255.0)
        
    return np.stack(crops, axis=0)


def validate_skin_guardrail(image_bgr: np.ndarray) -> Tuple[bool, str, dict]:
    """
    Validates input images to ensure they contain human skin before running CNN inference.
    Rejects out-of-distribution (OOD) inputs:
    - Overly dark, unilluminated, or blank images
    - Severely overexposed or pure white images
    - Radiographic scans (monochromatic X-rays, CT scans) with specific guidance to Pneumonia module
    - Printed documents, prescriptions, or signatures on white paper
    - Everyday non-skin images (sky, foliage, cars, objects, wallpapers) with low skin chromaticity

    Returns:
        (is_valid: bool, message: str, metadata: dict)
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    mean_val = float(np.mean(gray))
    std_val = float(np.std(gray))

    # Stage 1: Photometric Quality
    if mean_val < 18.0 or (mean_val < 30.0 and std_val < 6.0):
        return False, "The uploaded image is too dark or empty. Please ensure the skin area is clearly visible under adequate lighting.", {
            "rejection_type": "DARK_OR_BLANK",
            "mean_brightness": round(mean_val, 1),
            "std_brightness": round(std_val, 1)
        }
    if mean_val > 248.0 and std_val < 8.0:
        return False, "The uploaded image is severely overexposed or blank. Please upload a clear photo of the skin lesion or rash.", {
            "rejection_type": "OVEREXPOSED",
            "mean_brightness": round(mean_val, 1),
            "std_brightness": round(std_val, 1)
        }
    if std_val < 1.0:
        return False, "The uploaded image is a solid uniform color without visible skin texture. Please upload a clear clinical photograph.", {
            "rejection_type": "UNIFORM_SOLID",
            "mean_brightness": round(mean_val, 1),
            "std_brightness": round(std_val, 1)
        }

    # Stage 2: Radiographic / Monochromatic X-Ray Scan Check
    b, g, r = image_bgr[:, :, 0], image_bgr[:, :, 1], image_bgr[:, :, 2]
    chan_div = float((np.mean(np.abs(b.astype(float) - g.astype(float))) +
                      np.mean(np.abs(g.astype(float) - r.astype(float))) +
                      np.mean(np.abs(b.astype(float) - r.astype(float)))) / 3.0)
    
    if chan_div < 2.5:
        return False, "This image appears to be a radiographic scan or grayscale X-ray. For chest X-rays, please use the SwasthAI Pneumonia Assessment module.", {
            "rejection_type": "RADIOGRAPHIC_XRAY",
            "channel_divergence": round(chan_div, 2),
            "redirect_module": "pneumonia"
        }

    # Stage 3: Document / Prescription / Signature Check
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    sat_mean = float(np.mean(hsv[:, :, 1]))
    if sat_mean < 25.0 and chan_div < 12.0 and mean_val > 100.0:
        return False, "This image appears to be a document, prescription, or handwriting. Please upload a clinical photograph of human skin.", {
            "rejection_type": "DOCUMENT",
            "mean_saturation": round(sat_mean, 1),
            "channel_divergence": round(chan_div, 2)
        }

    # Stage 4: Human Skin Chrominance Verification (YCbCr + HSV)
    # Calibrated across all Fitzpatrick skin types (I-VI) and erythematous/purpuric lesions
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
    cr, cb = ycrcb[:, :, 1], ycrcb[:, :, 2]
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    skin_mask = (cr >= 125) & (cr <= 205) & (cb >= 60) & (cb <= 145) & (((h <= 28) | (h >= 160)) & (s >= 18) & (v >= 30))
    skin_cov = float(np.mean(skin_mask) * 100.0)

    if skin_cov < 30.0:
        return False, "No human skin detected in this image. Please upload a clear, focused photograph showing the affected skin condition.", {
            "rejection_type": "NON_SKIN",
            "skin_coverage": round(skin_cov, 1)
        }

    # Stage 5: Semantic Animal & Everyday Object Detection (ResNet-18)
    try:
        from PIL import Image
        import torch
        resnet_model, preprocess_fn, categories = _get_semantic_classifier()
        rgb_img = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)
        batch = preprocess_fn(pil_img).unsqueeze(0)
        with torch.no_grad():
            probs = torch.nn.functional.softmax(resnet_model(batch)[0], dim=0)
        top_prob, top_idx = torch.topk(probs, 1)
        p_val = float(top_prob[0].item())
        idx_val = int(top_idx[0].item())
        cat_name = categories[idx_val]

        # ImageNet Animal Categories (0-397, excluding 29 axolotl)
        is_animal = (0 <= idx_val <= 397) and (idx_val != 29)
        if is_animal and p_val >= 0.35:
            clean_name = cat_name.split(',')[0].strip()
            return False, f"An animal or non-human subject ({clean_name}) was detected in this image. SwasthAI Skin Assessment is calibrated exclusively for human clinical dermatology.", {
                "rejection_type": "ANIMAL",
                "detected_class": clean_name,
                "confidence": round(p_val, 2)
            }

        # Dominant clothing or apparel check
        clothing_keywords = ('coat', 'jacket', 'suit', 'cardigan', 'sweater', 'sweatshirt', 
                             'trench coat', 'jean', 'denim', 'jersey', 'fur coat', 'wool', 'sleeping bag')
        if any(kw in cat_name.lower() for kw in clothing_keywords) and p_val >= 0.50:
            clean_name = cat_name.split(',')[0].strip()
            return False, f"The image predominantly shows clothing or apparel ({clean_name}) rather than exposed skin. Please upload a clear photo focused on the affected skin area.", {
                "rejection_type": "CLOTHING",
                "detected_class": clean_name,
                "confidence": round(p_val, 2)
            }

        # Everyday objects (vehicles, electronics, furniture, buildings)
        object_keywords = ('car', 'motorcycle', 'bicycle', 'airplane', 'airliner', 'truck', 'bus', 
                           'train', 'boat', 'ship', 'laptop', 'computer', 'keyboard', 'screen', 
                           'cellular telephone', 'table', 'chair', 'sofa', 'building', 'church')
        if any(kw in cat_name.lower() for kw in object_keywords) and p_val >= 0.40:
            clean_name = cat_name.split(',')[0].strip()
            return False, f"An everyday object ({clean_name}) was detected in this image. Please upload a clinical photograph of human skin.", {
                "rejection_type": "OBJECT",
                "detected_class": clean_name,
                "confidence": round(p_val, 2)
            }
    except Exception:
        # Fallback gracefully if semantic classifier is unavailable
        pass

    # Stage 6: Distant Face / Full-Body Portrait Check
    # Clinical dermatology requires close-up framing. Distant portraits dilute lesions with clothes/background.
    try:
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        yunet_path = os.path.join(models_dir, "face_detection_yunet_2023mar.onnx")
        if os.path.exists(yunet_path):
            h_img, w_img = image_bgr.shape[:2]
            face_detector = cv2.FaceDetectorYN.create(yunet_path, "", (w_img, h_img))
            _, faces = face_detector.detect(image_bgr)
            if faces is not None and len(faces) > 0:
                max_face_area = max((float(f[2]) * float(f[3])) for f in faces)
                face_pct = (max_face_area / float(w_img * h_img)) * 100.0
                if face_pct < 12.0:
                    return False, f"Distant portrait or full-body photo detected (face occupies only {face_pct:.1f}% of the frame). Please crop tightly around the specific rash or skin lesion.", {
                        "rejection_type": "DISTANT_PORTRAIT",
                        "face_coverage": round(face_pct, 1)
                    }
    except Exception:
        pass

    return True, f"Valid skin image (skin coverage: {skin_cov:.1f}%)", {
        "skin_coverage": round(skin_cov, 1),
        "channel_divergence": round(chan_div, 2),
        "mean_brightness": round(mean_val, 1)
    }


_semantic_resnet = None
_semantic_preprocess = None
_semantic_categories = None

def _get_semantic_classifier():
    global _semantic_resnet, _semantic_preprocess, _semantic_categories
    if _semantic_resnet is None:
        from torchvision import models
        weights = models.ResNet18_Weights.DEFAULT
        _semantic_resnet = models.resnet18(weights=weights).eval()
        _semantic_preprocess = weights.transforms()
        _semantic_categories = weights.meta['categories']
    return _semantic_resnet, _semantic_preprocess, _semantic_categories



