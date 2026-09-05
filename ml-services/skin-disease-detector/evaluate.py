import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
from preprocessing import SkinLesionDataset, load_and_split_data, val_transforms, SKIN_CLASSES, INDEX_TO_CLASS
from train import create_model

def evaluate_model(model_path, data_dir, metadata_path, batch_size=32):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Load Data
    _, _, test_df = load_and_split_data(metadata_path)
    test_dataset = SkinLesionDataset(test_df, data_dir, transform=val_transforms)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    
    # Load Model
    model = create_model(len(SKIN_CLASSES)).to(device)
    checkpoint = torch.load(model_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    
    all_preds = []
    all_labels = []
    
    print("Running inference on test set...")
    with torch.no_grad():
        for inputs, labels in test_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            _, preds = outputs.max(1)
            
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            
    # Evaluation Metrics (Rule 9)
    target_names = [INDEX_TO_CLASS[i] for i in range(len(SKIN_CLASSES))]
    
    print("\nClassification Report:")
    print(classification_report(all_labels, all_preds, target_names=target_names))
    
    # Confusion Matrix
    cm = confusion_matrix(all_labels, all_preds)
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=target_names, yticklabels=target_names)
    plt.xlabel('Predicted')
    plt.ylabel('True')
    plt.title('Confusion Matrix - Skin Disease')
    plt.savefig('confusion_matrix.png')
    print("Saved confusion matrix plot to confusion_matrix.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Skin Disease CNN")
    parser.add_argument("--model", type=str, default="checkpoints/skin_disease_resnet50.pt", help="Path to checkpoint")
    parser.add_argument("--data_dir", type=str, nargs="+", default=["data/raw/HAM10000_images_part_1", "data/raw/HAM10000_images_part_2"], help="Paths to image directories")
    parser.add_argument("--metadata", type=str, default="data/raw/HAM10000_metadata.csv", help="Path to metadata CSV")
    args = parser.parse_args()
    
    evaluate_model(args.model, args.data_dir, args.metadata)
