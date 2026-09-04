"""
Loads images from split_manifest.csv (not the raw folder structure —
that had leaked patients, see rebuild_split.py).
"""
import csv
from pathlib import Path
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms

DATA_DIR = Path(__file__).parent / "data"
IMG_SIZE = 224
CLASS_TO_IDX = {"NORMAL": 0, "PNEUMONIA": 1}

# NOTE: using plain 0-1 scaling (no ImageNet mean/std) to match this
# project's backend preprocess_for_cnn() contract exactly.


def get_train_transforms():
    return transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ToTensor(),  # already scales to 0-1
    ])


def get_eval_transforms():
    return transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
    ])


class ManifestDataset(Dataset):
    def __init__(self, manifest_path, split, transform):
        self.samples = []
        with open(manifest_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["split"] == split:
                    self.samples.append((row["filepath"], CLASS_TO_IDX[row["class"]]))
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        img = self.transform(img)
        return img, label


def load_datasets():
    manifest_path = DATA_DIR / "split_manifest.csv"
    train_set = ManifestDataset(manifest_path, "train", get_train_transforms())
    val_set = ManifestDataset(manifest_path, "val", get_eval_transforms())
    test_set = ManifestDataset(manifest_path, "test", get_eval_transforms())
    return train_set, val_set, test_set


def make_loaders(train_set, val_set, test_set, batch_size=32):
    # num_workers=0 for Windows to avoid multiprocessing issues in scripts
    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=False, num_workers=0)
    return train_loader, val_loader, test_loader