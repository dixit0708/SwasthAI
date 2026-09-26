import csv
import os
from PIL import Image
import torch
from torch.utils.data import Dataset
import torchvision.transforms as transforms

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
        transforms.RandomApply([transforms.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.2, hue=0.05)], p=0.8), # Heavy lighting changes (flash, indoor light)
        transforms.RandomRotation(degrees=45),
        transforms.RandomPerspective(distortion_scale=0.2, p=0.3), # Slight perspective distortion from bad camera angles
        transforms.RandomApply([transforms.GaussianBlur(kernel_size=(5, 9), sigma=(0.1, 2.0))], p=0.3), # Out of focus phone shots
        transforms.RandomAdjustSharpness(sharpness_factor=2, p=0.3), # Over-sharpened phone processing
        transforms.ToTensor(),
        # Simulating sensor noise could be done after ToTensor but we'll stick to built-in transforms for simplicity
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
