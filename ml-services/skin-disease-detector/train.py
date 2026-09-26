import os
import csv
import time
from PIL import Image
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torchvision import models
import torchvision.transforms as transforms
from sklearn.metrics import classification_report, f1_score
import numpy as np
import pandas as pd

# ==========================================
# PREPROCESSING DEFINITIONS
# ==========================================
def get_train_transforms():
    """
    HEAVY AUGMENTATION Transforms for training split.
    Specifically designed to bridge the domain gap between clinical DermNet photos
    and real-world smartphone photos by simulating blur, bad lighting, diverse crops,
    and perspective warps.
    """
    return transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.5, 1.0)), # Simulate arbitrary zooming/cropping
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.2), # Some skin photos are taken upside down
        transforms.RandomApply([transforms.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.2, hue=0.05)], p=0.8), # Heavy lighting changes
        transforms.RandomRotation(degrees=45),
        transforms.RandomPerspective(distortion_scale=0.2, p=0.3), # Perspective distortion
        transforms.RandomApply([transforms.GaussianBlur(kernel_size=(5, 9), sigma=(0.1, 2.0))], p=0.3), # Out of focus phone shots
        transforms.RandomAdjustSharpness(sharpness_factor=2, p=0.3), # Over-sharpened phone processing
        transforms.ToTensor(),
    ])

def get_val_transforms():
    """
    Transforms for validation/test split.
    Uses aspect-preserving Resize to 256 followed by a CenterCrop to 224x224.
    """
    return transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor()
    ])

class ManifestDataset(Dataset):
    def __init__(self, manifest_path, split, transform, data_dir, class_to_idx):
        self.data_dir = data_dir
        self.samples = []
        self.targets = []
        with open(manifest_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["new_split"] == split:
                    full_path = os.path.join(data_dir, row["filepath"])
                    cls_idx = class_to_idx[row["class_name"]]
                    self.samples.append(full_path)
                    self.targets.append(cls_idx)
                    
        self.transform = transform
        self.classes = list(class_to_idx.keys())

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path = self.samples[idx]
        label = self.targets[idx]
        img = Image.open(path).convert("RGB")
        img = self.transform(img)
        return img, label


# ==========================================
# TRAINING LOGIC
# ==========================================
def train_model(data_dir=r"/content/data", num_epochs=40, batch_size=32, learning_rate=1e-4):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    manifest_path = os.path.join(data_dir, "split_manifest.csv")
    
    df = pd.read_csv(manifest_path)
    unique_classes = sorted(df['class_name'].unique())
    class_to_idx = {cls: idx for idx, cls in enumerate(unique_classes)}
    num_classes = len(unique_classes)
    
    train_dataset = ManifestDataset(manifest_path, "train", get_train_transforms(), data_dir, class_to_idx)
    val_dataset = ManifestDataset(manifest_path, "test", get_val_transforms(), data_dir, class_to_idx)
    
    class_names = train_dataset.classes
    
    class_counts = np.bincount(train_dataset.targets)
    class_weights = 1.0 / class_counts
    sample_weights = np.array([class_weights[t] for t in train_dataset.targets])
    sampler = WeightedRandomSampler(weights=sample_weights, num_samples=len(sample_weights), replacement=True)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, sampler=sampler, num_workers=2)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=2)
    
    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, num_classes)
    model = model.to(device)
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    
    # 3. Add a learning rate scheduler
    scheduler = ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=3)
    
    # Store checkpoint in Google Drive directly so it survives Colab restarts
    drive_checkpoint_dir = "/content/drive/MyDrive/SwasthAI_Skin_Data/checkpoints"
    os.makedirs(drive_checkpoint_dir, exist_ok=True)
    best_model_path = os.path.join(drive_checkpoint_dir, "best_resnet50_dermnet.pth")
    latest_model_path = os.path.join(drive_checkpoint_dir, "latest_epoch.pth")
    
    best_f1 = 0.0
    start_epoch = 0
    
    # 1. RESUME TRAINING LOGIC
    if os.path.exists(best_model_path):
        print(f"Found existing checkpoint at {best_model_path}. Resuming training for Robustness Fine-Tuning...")
        checkpoint = torch.load(best_model_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        
        # We purposely DO NOT load the old optimizer state. We want a fresh start
        # with the base learning_rate (1e-4) to adapt to the heavy augmentation.
        print(f"Starting fresh optimizer with LR={learning_rate} for new augmentation stage.")
            
        if "best_f1" in checkpoint:
            best_f1 = checkpoint["best_f1"]
        else:
            best_f1 = 0.5839 # Fallback based on last run
            
        if "epoch" in checkpoint:
            start_epoch = checkpoint["epoch"] + 1
        else:
            start_epoch = 20 # Fallback 
            
        # Give a fresh budget of 30 epochs for this new stage
        num_epochs = start_epoch + 30
            
        print(f"Resumed from epoch {start_epoch} with Best F1: {best_f1:.4f}. Extended budget to epoch {num_epochs}.")
    else:
        print("No checkpoint found. Starting from scratch.")

    # 2. EARLY STOPPING VARIABLES
    early_stopping_patience = 5
    epochs_without_improvement = 0
    best_report = ""
    
    for epoch in range(start_epoch, num_epochs):
        print(f"\nEpoch {epoch+1}/{num_epochs}")
        print("-" * 10)
        
        # Training phase
        model.train()
        running_loss = 0.0
        
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * inputs.size(0)
            
        epoch_loss = running_loss / len(train_dataset)
        print(f"Train Loss: {epoch_loss:.4f}")
        
        # Validation phase
        model.eval()
        val_loss = 0.0
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * inputs.size(0)
                
                _, preds = torch.max(outputs, 1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
                
        val_loss = val_loss / len(val_dataset)
        macro_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
        print(f"Val Loss: {val_loss:.4f} | Macro F1: {macro_f1:.4f}")
        
        # LEARNING RATE SCHEDULER STEP
        old_lr = optimizer.param_groups[0]['lr']
        if hasattr(scheduler, 'step'):
            scheduler.step(macro_f1)
        new_lr = optimizer.param_groups[0]['lr']
        if new_lr != old_lr:
            print(f"Learning rate adjusted: {old_lr} -> {new_lr}")
        
        # CHECK FOR IMPROVEMENT
        if macro_f1 > best_f1:
            print(f"New best Macro F1 score ({best_f1:.4f} --> {macro_f1:.4f}). Saving model...")
            best_f1 = macro_f1
            epochs_without_improvement = 0
            
            # Pack class_to_idx, optimizer, and epoch for future resumption
            checkpoint = {
                "model_state_dict": model.state_dict(),
                "class_to_idx": class_to_idx,
                "optimizer_state_dict": optimizer.state_dict(),
                "best_f1": best_f1,
                "epoch": epoch
            }
            torch.save(checkpoint, best_model_path)
            
            best_report = classification_report(all_labels, all_preds, target_names=class_names, zero_division=0)
        else:
            epochs_without_improvement += 1
            print(f"No improvement for {epochs_without_improvement} epoch(s).")
            
        # ==========================================
        # UNCONDITIONAL LATEST EPOCH SAVE
        # ==========================================
        latest_checkpoint = {
            "model_state_dict": model.state_dict(),
            "class_to_idx": class_to_idx,
            "optimizer_state_dict": optimizer.state_dict(),
            "best_f1": best_f1, 
            "epoch": epoch
        }
        torch.save(latest_checkpoint, latest_model_path)
        print(f"Saved unconditionally to {latest_model_path}")
            
        # EARLY STOPPING CHECK
        if epochs_without_improvement >= early_stopping_patience:
            print(f"\nEarly stopping triggered after {epoch+1} epochs! Validation F1 hasn't improved for {early_stopping_patience} consecutive epochs.")
            break
            
    print("\nTraining Complete.")
    print("Best Macro F1:", best_f1)
    
    # 4. Log to EXPERIMENTS.md in Google Drive
    exp_path = "/content/drive/MyDrive/SwasthAI_Skin_Data/EXPERIMENTS.md"
    try:
        with open(exp_path, "a") as f:
            f.write("\n## DermNet ResNet50 Fine-Tuning (Colab GPU) - ROBUSTNESS STAGE\n")
            f.write(f"- **Total Epochs Budget:** {num_epochs}\n")
            f.write(f"- **Final Best Macro F1:** {best_f1:.4f}\n")
            f.write(f"- **Additions:** Heavy Data Augmentation, LR Reset, Unconditional Epoch Save\n")
            if best_report:
                f.write("\n### Best Epoch Classification Report\n```text\n")
                f.write(best_report)
                f.write("\n```\n")
    except Exception as e:
        print("Could not log to EXPERIMENTS.md:", e)

if __name__ == '__main__':
    train_model()