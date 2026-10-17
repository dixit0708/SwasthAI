"""Skin Disease CNN (ResNet50) loading and inference."""
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

def predict_skin(model, idx_to_class: dict, preprocessed_image: np.ndarray, device: str = "cpu") -> dict:
    """
    Runs multi-scale pyramid inference on preprocessed numpy image array.
    Expects input shape: (N, H, W, C) or (H, W, C) where C is RGB and N is number of pyramid scales.
    Selects the scale with the most decisive, highest-confidence diagnostic signature.
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
    
    return {
        "label": idx_to_class[top1_idx],
        "confidence": float(probabilities[top1_idx]),
        "differential_diagnosis": differential
    }
