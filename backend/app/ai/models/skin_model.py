"""Skin Disease CNN (ResNet50) loading and inference."""
import os
import torch
import torch.nn as nn
from torchvision import models
import numpy as np
import scipy.stats

def build_skin_model(num_classes: int = 23):
    """Builds the ResNet50 model with custom classification head."""
    model = models.resnet50(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, num_classes)
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
    model = build_skin_model(num_classes=num_classes)
    
    # Support loading both full checkpoint dicts or just the state_dict
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.to(device)
    model.eval()
    
    # Invert mapping for predictions
    idx_to_class = {v: k for k, v in class_to_idx.items()}
    
    return model, idx_to_class

def predict_skin(model, idx_to_class: dict, preprocessed_image: np.ndarray, device: str = "cpu") -> dict:
    """
    Runs inference on a preprocessed numpy image array.
    Expects input shape: (1, H, W, C) where C is RGB.
    """
    import torch.nn.functional as F
    
    # Convert (B, H, W, C) -> (B, C, H, W) for PyTorch
    image_transposed = np.transpose(preprocessed_image, (0, 3, 1, 2))
    
    # Convert to PyTorch Tensor
    tensor_img = torch.tensor(image_transposed, dtype=torch.float32).to(device)
    
    # Run Inference
    with torch.no_grad():
        outputs = model(tensor_img)
        probabilities = F.softmax(outputs, dim=1)[0].cpu().numpy()
        
    max_p = float(np.max(probabilities))
    entropy = float(scipy.stats.entropy(probabilities))
    
    if max_p < 0.40 or entropy > 1.20:
        return {
            "prediction": "OOD", 
            "message": f"This image doesn't look like a clear, close-up photo of the skin condition - for better results, upload a well-lit, clearly focused image of the affected area."
        }
        
    pred_idx = int(np.argmax(probabilities))
    
    return {
        "label": idx_to_class[pred_idx],
        "confidence": max_p
    }
