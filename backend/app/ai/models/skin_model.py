"""Skin Disease CNN loading and inference."""
import os
import torch
import torch.nn as nn
from torchvision import models
import numpy as np

def build_skin_model(num_classes: int = 23, architecture: str = "densenet121"):
    """Builds the CNN model (DenseNet121 or ResNet50) with custom classification head."""
    if architecture == "resnet50":
        model = models.resnet50(weights=None)
        num_ftrs = model.fc.in_features
        model.fc = nn.Linear(num_ftrs, num_classes)
    else:
        model = models.densenet121(weights=None)
        num_ftrs = model.classifier.in_features
        model.classifier = nn.Linear(num_ftrs, num_classes)
        type(model).fc = property(lambda self: self.classifier)
    return model

def load_skin_model(ckpt_path: str, device: str = "cpu"):
    """Loads the pre-trained model weights from the given checkpoint."""
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(f"Model checkpoint not found at {ckpt_path}")

    checkpoint = torch.load(ckpt_path, map_location=device)
    class_to_idx = checkpoint.get("class_to_idx")
    if not class_to_idx:
        raise ValueError("Checkpoint is missing 'class_to_idx' mapping.")
        
    num_classes = len(class_to_idx)
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    
    # Auto-detect architecture from checkpoint layer names
    if any("classifier" in k for k in state_dict.keys()):
        arch = "densenet121"
    else:
        arch = "resnet50"
        
    model = build_skin_model(num_classes=num_classes, architecture=arch)
    model.load_state_dict(state_dict)

    model.to(device)
    model.eval()
    
    idx_to_class = {v: k for k, v in class_to_idx.items()}
    return model, idx_to_class

def generate_gradcam_overlay(model, tensor_scale_img: torch.Tensor, target_class_idx: int, original_bgr: np.ndarray, device: str = "cpu") -> str:
    """
    Computes Grad-CAM feature attribution on the best pyramid scale and maps it onto the original image.
    Returns base64 data URL string: 'data:image/jpeg;base64,...'
    """
    import cv2
    import base64
    import torch.nn.functional as F

    try:
        tensor = tensor_scale_img.clone().detach().to(device)
        tensor.requires_grad = True

        gradients = []
        def save_grad(g):
            gradients.append(g)

        # DenseNet121 features extractor
        if hasattr(model, 'features'):
            features = model.features(tensor)
            features.register_hook(save_grad)
            out = F.relu(features, inplace=False)
            out = F.adaptive_avg_pool2d(out, (1, 1))
            out = torch.flatten(out, 1)
            logits = model.classifier(out)
        else:
            # ResNet architecture fallback
            features = None
            def hook(m, i, o):
                nonlocal features
                features = o
                o.register_hook(save_grad)
            h = model.layer4.register_forward_hook(hook)
            logits = model(tensor)
            h.remove()

        model.zero_grad()
        logits[0, target_class_idx].backward()

        if not gradients or features is None:
            return None

        grads = gradients[0][0].detach().cpu().numpy()
        acts = features[0].detach().cpu().numpy()
        weights = np.mean(grads, axis=(1, 2))

        cam = np.zeros(acts.shape[1:], dtype=np.float32)
        for i, w in enumerate(weights):
            cam += w * acts[i]

        cam = np.maximum(cam, 0)
        if np.max(cam) > 0:
            cam = cam / np.max(cam)

        h_orig, w_orig = original_bgr.shape[:2]
        cam_resized = cv2.resize(cam, (w_orig, h_orig))
        heatmap = cv2.applyColorMap(np.uint8(255 * cam_resized), cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(original_bgr, 0.65, heatmap, 0.35, 0)

        success, encoded_img = cv2.imencode('.jpg', overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success:
            return None
        b64_str = base64.b64encode(encoded_img).decode('utf-8')
        return f"data:image/jpeg;base64,{b64_str}"
    except Exception as e:
        # Fallback gracefully if CAM fails
        return None


def predict_skin(
    model, 
    idx_to_class: dict, 
    preprocessed_image: np.ndarray, 
    original_image_bgr: np.ndarray = None, 
    device: str = "cpu"
) -> dict:
    """
    Runs multi-scale pyramid inference on preprocessed numpy image array.
    Expects input shape: (N, H, W, C) or (H, W, C) where C is RGB and N is number of pyramid scales.
    Selects the scale with the most decisive, highest-confidence diagnostic signature.
    Also generates Grad-CAM lesion heatmap overlay on original image if provided.
    """
    import torch.nn.functional as F
    
    if preprocessed_image.ndim == 3:
        preprocessed_image = np.expand_dims(preprocessed_image, axis=0)
        
    image_transposed = np.transpose(preprocessed_image, (0, 3, 1, 2))
    tensor_img = torch.tensor(image_transposed, dtype=torch.float32).to(device)
    
    with torch.no_grad():
        outputs = model(tensor_img)
        probabilities_batch = F.softmax(outputs, dim=1) # shape: (N, 23)
        
        # Select the pyramid scale with the highest peak confidence
        max_per_scale = torch.max(probabilities_batch, dim=1)[0]
        best_scale_idx = torch.argmax(max_per_scale).item()
        probabilities = probabilities_batch[best_scale_idx].cpu().numpy()
        
    top3_indices = np.argsort(probabilities)[::-1][:3]
    top1_idx = int(top3_indices[0])
    
    differential = []
    for idx in top3_indices:
        differential.append({
            "label": idx_to_class[int(idx)],
            "confidence": float(probabilities[idx]),
            "percentage": round(float(probabilities[idx]) * 100, 1)
        })
    
    result = {
        "label": idx_to_class[top1_idx],
        "confidence": float(probabilities[top1_idx]),
        "differential_diagnosis": differential
    }

    # Generate Grad-CAM lesion heatmap attribution if original image is provided
    if original_image_bgr is not None:
        best_tensor = tensor_img[best_scale_idx:best_scale_idx+1]
        heatmap_url = generate_gradcam_overlay(model, best_tensor, top1_idx, original_image_bgr, device=device)
        if heatmap_url:
            result["heatmap_overlay"] = heatmap_url

    return result

