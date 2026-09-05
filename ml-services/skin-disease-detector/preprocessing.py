import os
import torch
import pandas as pd
import numpy as np
import cv2
from sklearn.model_selection import GroupShuffleSplit
from torchvision import transforms
from torch.utils.data import Dataset
from PIL import Image

# HAM10000 classes
SKIN_CLASSES = {
    'akiec': 0, # Actinic keratoses and intraepithelial carcinoma
    'bcc': 1,   # basal cell carcinoma
    'bkl': 2,   # benign keratosis-like lesions
    'df': 3,    # dermatofibroma
    'nv': 4,    # melanocytic nevi
    'vasc': 5,  # vascular lesions
    'mel': 6    # melanoma
}
INDEX_TO_CLASS = {v: k for k, v in SKIN_CLASSES.items()}

# Common transformations for training (includes augmentation)
train_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(20),
    transforms.ColorJitter(brightness=0.1, contrast=0.1),
    transforms.ToTensor()
])

# Transformations for validation/testing (no augmentation)
val_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor()
])

class SkinLesionDataset(Dataset):
    def __init__(self, df, img_dir, transform=None):
        """
        Args:
            df (pandas.DataFrame): DataFrame containing 'image_id' and 'dx' (class label).
            img_dir (str or list): Directory or list of directories with all the images.
            transform (callable, optional): Optional transform to be applied on a sample.
        """
        self.df = df
        self.img_dirs = [img_dir] if isinstance(img_dir, str) else img_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()

        img_id = self.df.iloc[idx]['image_id']
        img_name = None
        for d in self.img_dirs:
            potential_path = os.path.join(d, f"{img_id}.jpg")
            if os.path.exists(potential_path):
                img_name = potential_path
                break
        
        if img_name is None:
            raise FileNotFoundError(f"Image {img_id}.jpg not found in any of the provided directories.")

        image = Image.open(img_name).convert('RGB')
        label = SKIN_CLASSES[self.df.iloc[idx]['dx']]

        if self.transform:
            image = self.transform(image)

        return image, label

def load_and_split_data(metadata_csv, test_size=0.2, val_size=0.1):
    """
    Loads the HAM10000 metadata CSV and splits it into train, val, and test,
    ensuring no lesion_id leakage across splits.
    """
    df = pd.read_csv(metadata_csv)
    
    # Use GroupShuffleSplit to split based on lesion_id
    gss_test = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
    train_val_idx, test_idx = next(gss_test.split(df, groups=df['lesion_id']))
    
    train_val_df = df.iloc[train_val_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)
    
    # Adjust val size proportionally to remaining train data
    val_ratio = val_size / (1.0 - test_size)
    gss_val = GroupShuffleSplit(n_splits=1, test_size=val_ratio, random_state=42)
    train_idx, val_idx = next(gss_val.split(train_val_df, groups=train_val_df['lesion_id']))
    
    train_df = train_val_df.iloc[train_idx].reset_index(drop=True)
    val_df = train_val_df.iloc[val_idx].reset_index(drop=True)
    
    print(f"Train size: {len(train_df)}, Val size: {len(val_df)}, Test size: {len(test_df)}")
    
    # Sanity check for lesion_id leakage
    train_lesions = set(train_df['lesion_id'])
    val_lesions = set(val_df['lesion_id'])
    test_lesions = set(test_df['lesion_id'])
    
    assert train_lesions.isdisjoint(val_lesions), "Leakage detected between train and val splits!"
    assert train_lesions.isdisjoint(test_lesions), "Leakage detected between train and test splits!"
    assert val_lesions.isdisjoint(test_lesions), "Leakage detected between val and test splits!"
    print("Sanity check passed: No lesion_id overlaps across splits.")
    
    return train_df, val_df, test_df
