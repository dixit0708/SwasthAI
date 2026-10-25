"""Skin Disease CNN (ResNet50) loading and inference.

torch and torchvision are imported lazily inside each function, mirroring the
same pattern used in pneumonia_cnn.py, to avoid paying the ~230 MB RSS import
cost on worker processes that may never serve a skin-disease request.

Checkpoint expected at:
    ml-services/skin-disease-detector/checkpoints/skin_disease_resnet50.pt

Until the model is trained and that file exists, load_skin_model() raises
FileNotFoundError (caught in app/main.py's lifespan, which sets
app.state.skin_model = None and logs a warning).
"""

import os
import numpy as np

# 7 HAM10000 classes used during training.
SKIN_CLASS_NAMES = [
    "Melanocytic nevi",
    "Melanoma",
    "Benign keratosis-like lesions",
    "Basal cell carcinoma",
    "Actinic keratoses",
    "Vascular lesions",
    "Dermatofibroma",
]


def build_skin_model(num_classes: int = 7):
    """Builds a ResNet50 model with a custom classification head."""
    import torch.nn as nn
    from torchvision.models import resnet50

    model = resnet50(weights=None)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def load_skin_model(ckpt_path: str, num_classes: int = 7, device: str = "cpu"):
    """Loads pre-trained skin-disease model weights from *ckpt_path*.

    Raises FileNotFoundError if the checkpoint does not exist so that the
    caller (app/main.py lifespan) can log a warning and set the model to None
    rather than crashing startup.
    """
    import torch

    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(
            f"Skin Disease CNN checkpoint not found at {ckpt_path}. "
            "Train the model first via ml_pipeline/ (or ml-services/skin-disease-detector/)."
        )

    model = build_skin_model(num_classes=num_classes)
    checkpoint = torch.load(ckpt_path, map_location=device)

    # Support both raw state-dict and full checkpoint dicts.
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.to(device)
    model.eval()
    return model


def predict_skin_disease(
    model,
    preprocessed_image: np.ndarray,
    device: str = "cpu",
) -> dict:
    """Runs inference on a preprocessed image array.

    Args:
        model: Loaded PyTorch ResNet50 model (eval mode).
        preprocessed_image: Shape (1, H, W, C) float32 numpy array,
            normalised to [0, 1].  The same format produced by
            app/ai/inference/image_processing.py::preprocess_for_cnn().
        device: Torch device string.

    Returns:
        dict with keys:
            prediction  – top predicted class name (str)
            confidence  – probability of top class (float 0–1)
            all_scores  – {class_name: probability} for all 7 classes
    """
    import torch
    import torch.nn.functional as F

    # (B, H, W, C) → (B, C, H, W)
    image_transposed = np.transpose(preprocessed_image, (0, 3, 1, 2))
    tensor_img = torch.tensor(image_transposed, dtype=torch.float32).to(device)

    with torch.no_grad():
        logits = model(tensor_img)
        probabilities = F.softmax(logits, dim=1)[0]

    pred_idx = int(torch.argmax(probabilities).item())
    confidence = float(probabilities[pred_idx].item())

    all_scores = {
        name: float(probabilities[i].item())
        for i, name in enumerate(SKIN_CLASS_NAMES)
    }

    return {
        "prediction": SKIN_CLASS_NAMES[pred_idx],
        "confidence": confidence,
        "all_scores": all_scores,
    }
