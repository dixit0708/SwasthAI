import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import models
from preprocessing import SkinLesionDataset, load_and_split_data, train_transforms, val_transforms, SKIN_CLASSES, INDEX_TO_CLASS
from tqdm import tqdm
import argparse

def create_model(num_classes):
    # Using ResNet50 as a strong baseline for Skin Lesions
    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    
    # Freeze early layers if desired (optional, not doing it for full finetuning)
    num_ftrs = model.fc.in_features
    # Replace the final fully connected layer for our 7 classes
    model.fc = nn.Linear(num_ftrs, num_classes)
    return model

def train_epoch(model, dataloader, criterion, optimizer, device):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    pbar = tqdm(dataloader, desc="Training")
    for inputs, labels in pbar:
        inputs, labels = inputs.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        
        loss.backward()
        optimizer.step()
        
        running_loss += loss.item() * inputs.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
        
        pbar.set_postfix({'Loss': loss.item(), 'Acc': correct/total})
        
    epoch_loss = running_loss / len(dataloader.dataset)
    epoch_acc = correct / total
    return epoch_loss, epoch_acc

def validate_epoch(model, dataloader, criterion, device):
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    with torch.no_grad():
        pbar = tqdm(dataloader, desc="Validation")
        for inputs, labels in pbar:
            inputs, labels = inputs.to(device), labels.to(device)
            
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item() * inputs.size(0)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            
    epoch_loss = running_loss / len(dataloader.dataset)
    epoch_acc = correct / total
    return epoch_loss, epoch_acc

def main():
    parser = argparse.ArgumentParser(description="Train Skin Disease CNN")
    parser.add_argument("--data_dir", type=str, nargs="+", default=["data/raw/HAM10000_images_part_1", "data/raw/HAM10000_images_part_2"], help="Paths to image directories")
    parser.add_argument("--metadata", type=str, default="data/raw/HAM10000_metadata.csv", help="Path to metadata CSV")
    parser.add_argument("--epochs", type=int, default=15, help="Number of epochs to train")
    parser.add_argument("--batch_size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # 1. Load Data
    print("Loading data splits...")
    train_df, val_df, test_df = load_and_split_data(args.metadata)
    
    train_dataset = SkinLesionDataset(train_df, args.data_dir, transform=train_transforms)
    val_dataset = SkinLesionDataset(val_df, args.data_dir, transform=val_transforms)
    
    # Important: Handling class imbalance via WeightedRandomSampler or CrossEntropyLoss weights
    # For simplicity here, we use class weights in CrossEntropyLoss
    class_counts = train_df['dx'].value_counts().to_dict()
    # Compute inverse class frequencies
    weights = [1.0 / class_counts.get(INDEX_TO_CLASS[i], 1) for i in range(len(SKIN_CLASSES))]
    weights = torch.FloatTensor(weights).to(device)
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)
    
    # 2. Setup Model
    num_classes = len(SKIN_CLASSES)
    model = create_model(num_classes).to(device)
    
    # 3. Setup Loss and Optimizer
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    
    # 4. Training Loop
    best_val_acc = 0.0
    os.makedirs("checkpoints", exist_ok=True)
    
    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch+1}/{args.epochs}")
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = validate_epoch(model, val_loader, criterion, device)
        
        print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}")
        print(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            checkpoint = {
                "model_state_dict": model.state_dict(),
                "class_to_idx": SKIN_CLASSES
            }
            torch.save(checkpoint, "checkpoints/skin_disease_resnet50.pt")
            print("Saved new best model!")

if __name__ == "__main__":
    main()
