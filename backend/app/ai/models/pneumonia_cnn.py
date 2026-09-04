import torch
import torch.nn as nn
from torchvision.models import resnet18
import numpy as np
import os
from pathlib import Path

def build_pneumonia_model() -> nn.Module:
    """Builds the ResNet18 model with custom classification head (2 classes)."""
    model = resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 2)
    return model

def load_pneumonia_model(ckpt_path: str, device: str = "cpu") -> nn.Module:
    """Loads the pre-trained model weights from the given checkpoint."""
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(f"Model checkpoint not found at {ckpt_path}")
        
    model = build_pneumonia_model()
    checkpoint = torch.load(ckpt_path, map_location=device)
    
    # Support loading both full checkpoint dicts or just the state_dict
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)
        
    model.to(device)
    model.eval()
    return model

def predict_pneumonia(model: nn.Module, preprocessed_image: np.ndarray, device: str = "cpu") -> dict:
    """
    Runs inference on a preprocessed numpy image array.
    Expects input shape: (1, H, W, C).
    """
    # Convert (B, H, W, C) -> (B, C, H, W) for PyTorch
    image_transposed = np.transpose(preprocessed_image, (0, 3, 1, 2))
    
    # Convert to PyTorch Tensor
    tensor_img = torch.tensor(image_transposed, dtype=torch.float32).to(device)
    
    # Run Inference
    with torch.no_grad():
        outputs = model(tensor_img)
        probabilities = torch.nn.functional.softmax(outputs, dim=1)[0]
        
    class_names = {0: "NORMAL", 1: "PNEUMONIA"}
    pred_idx = torch.argmax(probabilities).item()
    confidence = probabilities[pred_idx].item()
    
    return {
        "prediction": class_names[pred_idx],
        "confidence": float(confidence)
    }
