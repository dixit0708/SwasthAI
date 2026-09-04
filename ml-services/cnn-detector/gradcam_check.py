"""
Grad-CAM sanity check — run this AFTER train.py, BEFORE trusting the model.

Generates heatmaps showing where the model "looks" when predicting.
Save to gradcam_output/ for visual inspection: heat should be on the
lungs, not on corners/borders/medical hardware.

Usage:
    python gradcam_check.py --num_samples 10
"""
import argparse
import csv
from pathlib import Path

import torch
import torch.nn as nn
import numpy as np
from torchvision.models import resnet18
from PIL import Image
import matplotlib.pyplot as plt

from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image

from preprocessing import get_eval_transforms, DATA_DIR

CKPT_PATH = Path(__file__).parent / "checkpoints" / "resnet18_finetuned.pt"
OUT_DIR = Path(__file__).parent / "gradcam_output"


def load_model():
    checkpoint = torch.load(CKPT_PATH, map_location="cpu")
    model = resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 2)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def get_test_pneumonia_samples(n):
    manifest_path = DATA_DIR / "split_manifest.csv"
    samples = []
    with open(manifest_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["split"] == "test" and row["class"] == "PNEUMONIA":
                samples.append(row["filepath"])
    return samples[:n]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_samples", type=int, default=10)
    args = parser.parse_args()

    if not CKPT_PATH.exists():
        print(f"ERROR: {CKPT_PATH} not found. Run train.py first.")
        return

    model = load_model()
    target_layer = model.layer4[-1]
    cam = GradCAM(model=model, target_layers=[target_layer])

    image_paths = get_test_pneumonia_samples(args.num_samples)
    if not image_paths:
        print("ERROR: no PNEUMONIA test images found in split_manifest.csv")
        return

    OUT_DIR.mkdir(exist_ok=True)
    transform = get_eval_transforms()

    for i, img_path in enumerate(image_paths):
        raw = Image.open(img_path).convert("RGB")
        input_tensor = transform(raw).unsqueeze(0)

        grayscale_cam = cam(input_tensor=input_tensor, targets=None)[0]

        rgb_img = np.array(raw.resize((224, 224))) / 255.0
        visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)

        fig, axes = plt.subplots(1, 2, figsize=(8, 4))
        axes[0].imshow(rgb_img)
        axes[0].set_title("Original")
        axes[0].axis("off")
        axes[1].imshow(visualization)
        axes[1].set_title("Grad-CAM")
        axes[1].axis("off")
        out_path = OUT_DIR / f"gradcam_{i}.png"
        plt.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved {out_path}")

    print(f"\n{len(image_paths)} heatmaps saved to {OUT_DIR}/")
    print("\nManually open each PNG and check:")
    print("  - Heat concentrated INSIDE lung fields -> trustworthy")
    print("  - Heat on borders, corners, wires/hardware, outside ribcage -> shortcut learning risk")


if __name__ == "__main__":
    main()