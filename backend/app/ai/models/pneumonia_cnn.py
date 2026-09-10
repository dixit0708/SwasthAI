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


def load_ood_stats(stats_path: str, device: str = "cpu"):
    """Loads Mahalanobis OOD statistics from an npz file."""
    if not os.path.exists(stats_path):
        return None
        
    import torch
    stats = np.load(stats_path)
    return {
        "mu_normal": torch.tensor(stats['mu_normal'], dtype=torch.float32).to(device).unsqueeze(0),
        "mu_pneumonia": torch.tensor(stats['mu_pneumonia'], dtype=torch.float32).to(device).unsqueeze(0),
        "inv_cov_matrix": torch.tensor(stats['inv_cov_matrix'], dtype=torch.float32).to(device),
        "threshold": float(stats['threshold'])
    }


def predict_pneumonia(model, preprocessed_image: np.ndarray, original_image: np.ndarray = None, ood_stats: dict = None, device: str = "cpu") -> dict:
    """
    Runs inference on a preprocessed numpy image array.
    Expects input shape: (1, H, W, C).
    If ood_stats and original_image are provided, performs Ensemble OOD detection first
    using Mahalanobis distance and HSV saturation.
    """
    import torch
    import torch.nn.functional as F
    import cv2

    # Convert (B, H, W, C) -> (B, C, H, W) for PyTorch
    image_transposed = np.transpose(preprocessed_image, (0, 3, 1, 2))

    # Convert to PyTorch Tensor
    tensor_img = torch.tensor(image_transposed, dtype=torch.float32).to(device)

    # Run Inference
    with torch.no_grad():
        # Extract penultimate features manually
        x = model.conv1(tensor_img)
        x = model.bn1(x)
        x = model.relu(x)
        x = model.maxpool(x)

        x = model.layer1(x)
        x = model.layer2(x)
        x = model.layer3(x)
        x = model.layer4(x)

        x = model.avgpool(x)
        feat = torch.flatten(x, 1)

        # Ensemble OOD Check
        if ood_stats is not None and original_image is not None:
            # Signal 1: Mahalanobis Distance
            mu_n = ood_stats["mu_normal"]
            mu_p = ood_stats["mu_pneumonia"]
            inv_cov = ood_stats["inv_cov_matrix"]
            
            diff_n = feat - mu_n
            dist_n = torch.matmul(torch.matmul(diff_n, inv_cov), diff_n.t()).item()
            
            diff_p = feat - mu_p
            dist_p = torch.matmul(torch.matmul(diff_p, inv_cov), diff_p.t()).item()
            
            min_dist = min(dist_n, dist_p)
            
            # Signal 2: Mean Saturation
            hsv = cv2.cvtColor(original_image, cv2.COLOR_BGR2HSV)
            mean_saturation = hsv[:, :, 1].mean()
            
            # Thresholds
            MAHALANOBIS_THRESHOLD = 2000.0
            SATURATION_THRESHOLD = 100.0
            
            # Signal 3: Face Detection (Using YuNet for OpenCV 5 compatibility)
            import os
            onnx_path = os.path.join(os.path.dirname(__file__), 'face_detection_yunet_2023mar.onnx')
            h, w, _ = original_image.shape
            face_detector = cv2.FaceDetectorYN.create(onnx_path, "", (w, h))
            _, faces = face_detector.detect(original_image)
            face_detected = faces is not None and len(faces) > 0
            
            if min_dist > MAHALANOBIS_THRESHOLD or mean_saturation > SATURATION_THRESHOLD or face_detected:
                return {
                    "prediction": "OOD",
                    "confidence": 0.0,
                    "message": "This image doesn't appear to be a valid chest X-ray" + (" (Face Detected)" if face_detected else ""),
                    "distance": min_dist,
                    "saturation": mean_saturation
                }

        # Final Classification
        outputs = model.fc(feat)
        probabilities = F.softmax(outputs, dim=1)[0]

    class_names = {0: "NORMAL", 1: "PNEUMONIA"}
    pred_idx = torch.argmax(probabilities).item()
    confidence = probabilities[pred_idx].item()

    return {
        "prediction": class_names[pred_idx],
        "confidence": float(confidence)
    }
