"""Pneumonia CNN (ResNet18) loading and inference.

torch and torchvision are imported lazily, inside each function rather than
at module level. Together they cost roughly 230MB of RSS to import (measured
locally: torch ~153MB, torchvision ~81MB) — merely importing this module at
FastAPI startup used to pay that cost on every worker process even before a
single pneumonia request arrived. Deferring the import to first actual use
(see the lazy-load-and-cache wiring in app/api/v1/endpoints/predict.py)
keeps a cold-started, pneumonia-unused process light.
"""
import os

import numpy as np


def build_pneumonia_model():
    """Builds the ResNet18 model with custom classification head (2 classes)."""
    import torch.nn as nn
    from torchvision.models import resnet18

    model = resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 2)
    return model


def load_pneumonia_model(ckpt_path: str, device: str = "cpu"):
    """Loads the pre-trained model weights from the given checkpoint."""
    import torch

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


def predict_pneumonia(model, preprocessed_image: np.ndarray, device: str = "cpu") -> dict:
    """
    Runs inference on a preprocessed numpy image array.
    Expects input shape: (1, H, W, C).
    """
    import torch
    import torch.nn.functional as F

    # Convert (B, H, W, C) -> (B, C, H, W) for PyTorch
    image_transposed = np.transpose(preprocessed_image, (0, 3, 1, 2))

    # Convert to PyTorch Tensor
    tensor_img = torch.tensor(image_transposed, dtype=torch.float32).to(device)

    # Run Inference
    with torch.no_grad():
        outputs = model(tensor_img)
        probabilities = F.softmax(outputs, dim=1)[0]

    class_names = {0: "NORMAL", 1: "PNEUMONIA"}
    pred_idx = torch.argmax(probabilities).item()
    confidence = probabilities[pred_idx].item()

    return {
        "prediction": class_names[pred_idx],
        "confidence": float(confidence)
    }
