import os
import torch
import cv2
import numpy as np
import pandas as pd
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
import argparse

from preprocessing import SkinLesionDataset, load_and_split_data, val_transforms, SKIN_CLASSES, INDEX_TO_CLASS
from train import create_model

def ensure_dir(d):
    if not os.path.exists(d):
        os.makedirs(d)

def run_gradcam(model_path, data_dirs, metadata_path, out_dir):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Load test split
    _, _, test_df = load_and_split_data(metadata_path)
    
    # Pick a few samples representing different classes (especially rare ones)
    sample_size_per_class = 3
    test_samples = []
    
    # We want at least df, vasc, akiec
    rare_classes = ['df', 'vasc', 'akiec']
    for cls in rare_classes:
        cls_df = test_df[test_df['dx'] == cls]
        test_samples.append(cls_df.head(sample_size_per_class))
        
    # Also add some common classes
    for cls in ['nv', 'mel', 'bcc', 'bkl']:
        cls_df = test_df[test_df['dx'] == cls]
        test_samples.append(cls_df.head(2))
        
    test_samples = pd.concat(test_samples).reset_index(drop=True)
    print(f"Running Grad-CAM on {len(test_samples)} test samples...")
    
    # Setup dataset to get images
    dataset = SkinLesionDataset(test_samples, data_dirs, transform=val_transforms)
    
    # Load Model
    model = create_model(len(SKIN_CLASSES)).to(device)
    checkpoint = torch.load(model_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    
    # Setup Grad-CAM
    # For ResNet50, the last conv layer is layer4[-1]
    target_layers = [model.layer4[-1]]
    cam = GradCAM(model=model, target_layers=target_layers) # Removed use_cuda as it's deprecated in newer versions and relies on tensor device
    
    ensure_dir(out_dir)
    
    for idx in range(len(dataset)):
        input_tensor, true_label = dataset[idx]
        input_tensor = input_tensor.unsqueeze(0).to(device)
        
        # We target the true label
        targets = [ClassifierOutputTarget(true_label)]
        
        grayscale_cam = cam(input_tensor=input_tensor, targets=targets)
        grayscale_cam = grayscale_cam[0, :]
        
        # To overlay, we need original image in range 0-1
        # The ToTensor transform already puts it in 0-1 (we removed Normalize in fix 2)
        rgb_img = input_tensor.squeeze().cpu().permute(1, 2, 0).numpy()
        
        visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)
        
        # Save output
        true_class_name = INDEX_TO_CLASS[true_label]
        img_id = test_samples.iloc[idx]['image_id']
        
        out_path = os.path.join(out_dir, f"gradcam_{img_id}_{true_class_name}.png")
        # Convert RGB to BGR for cv2.imwrite
        visualization_bgr = cv2.cvtColor(visualization, cv2.COLOR_RGB2BGR)
        cv2.imwrite(out_path, visualization_bgr)
        print(f"Saved {out_path}")

    print("\n=======================================================")
    print("WARNING: EXPLAINABILITY CHECK REQUIRED!")
    print("Skin lesion classifiers often learn 'shortcut' features:")
    print(" - Surgical ink markings or rulers")
    print(" - Dark borders/vignettes from dermatoscopes")
    print(" - Hair density or lighting artifacts")
    print(f"Please manually inspect the heatmaps generated in '{out_dir}/'")
    print("to verify the model is actually focusing on the lesion.")
    print("=======================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="checkpoints/skin_disease_resnet50.pt")
    parser.add_argument("--data_dir", type=str, nargs="+", default=["data/raw/HAM10000_images_part_1", "data/raw/HAM10000_images_part_2"])
    parser.add_argument("--metadata", type=str, default="data/raw/HAM10000_metadata.csv")
    parser.add_argument("--out_dir", type=str, default="gradcam_output")
    args = parser.parse_args()
    
    run_gradcam(args.model, args.data_dir, args.metadata, args.out_dir)
