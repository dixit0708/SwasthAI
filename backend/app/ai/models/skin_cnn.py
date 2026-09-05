import torch
import torch.nn as nn
from torchvision import models
import logging

logger = logging.getLogger(__name__)

# HAM10000 classes mapped to readable labels
SKIN_CLASSES_READABLE = {
    0: "Actinic keratoses and intraepithelial carcinoma (akiec)",
    1: "Basal cell carcinoma (bcc)",
    2: "Benign keratosis-like lesions (bkl)",
    3: "Dermatofibroma (df)",
    4: "Melanocytic nevi (nv) - Benign",
    5: "Vascular lesions (vasc)",
    6: "Melanoma (mel) - Malignant"
}

def load_skin_model(ckpt_path: str, num_classes: int = 7) -> nn.Module:
    """
    Loads the trained Skin Disease CNN (ResNet50) from the checkpoint.
    """
    try:
        model = models.resnet50(weights=None)
        num_ftrs = model.fc.in_features
        model.fc = nn.Linear(num_ftrs, num_classes)
        
        # Determine device (CPU for most backend setups unless GPU is specifically configured)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        model.load_state_dict(torch.load(ckpt_path, map_location=device))
        model.to(device)
        model.eval()
        return model
    except Exception as e:
        logger.error(f"Error loading Skin Disease model: {e}")
        raise e

def predict_skin_disease(model: nn.Module, preprocessed_img: torch.Tensor) -> dict:
    """
    Runs inference on the preprocessed image.
    Follows Rule 11 (Medical Safety) by returning insights/risk assessments.
    """
    device = next(model.parameters()).device
    inputs = preprocessed_img.to(device)
    
    with torch.no_grad():
        outputs = model(inputs)
        probabilities = torch.nn.functional.softmax(outputs, dim=1)
        
        # Get the predicted class and confidence
        confidence, predicted_idx = torch.max(probabilities, 1)
        pred_class_idx = predicted_idx.item()
        conf_val = confidence.item()
        
    class_name = SKIN_CLASSES_READABLE.get(pred_class_idx, "Unknown")
    
    return {
        "status": "success",
        "insight_type": "Skin Disease Risk Assessment",
        "prediction": class_name,
        "confidence": float(conf_val),
        "disclaimer": "This is an AI-generated insight and not a definitive medical diagnosis. Please consult a dermatologist."
    }
