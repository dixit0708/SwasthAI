"""
Train the pneumonia CNN detector (CPU-friendly baseline).

Baseline (last layer only):
    python train.py --epochs 5

Fine-tune (unfreezes deeper layers — use if Grad-CAM showed shortcut learning):
    python train.py --epochs 5 --finetune --lr 5e-5
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
from torch.optim import Adam
from torchvision.models import resnet18, ResNet18_Weights
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, confusion_matrix
from tqdm import tqdm

from preprocessing import load_datasets, make_loaders

CKPT_DIR = Path(__file__).parent / "checkpoints"
LOG_FILE = Path(__file__).parent / "EXPERIMENTS.md"


def build_model(finetune: bool):
    model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
    for param in model.parameters():
        param.requires_grad = False  # freeze everything by default

    if finetune:
        # unfreeze the last two residual blocks — lets the model learn
        # actual texture/pattern features instead of relying only on
        # the frozen generic ImageNet features
        for name, module in model.named_children():
            if name in ("layer3", "layer4"):
                for param in module.parameters():
                    param.requires_grad = True

    model.fc = nn.Linear(model.fc.in_features, 2)
    for param in model.fc.parameters():
        param.requires_grad = True  # always train the new head
    return model


def compute_class_weights(train_set):
    counts = {0: 0, 1: 0}
    for _, label in train_set.samples:
        counts[label] += 1
    total = sum(counts.values())
    weights = [total / (2 * counts[i]) for i in range(2)]
    return torch.tensor(weights, dtype=torch.float32)


def evaluate(model, loader):
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for images, labels in loader:
            outputs = model(images)
            preds = outputs.argmax(dim=1)
            all_preds.extend(preds.tolist())
            all_labels.extend(labels.tolist())

    acc = accuracy_score(all_labels, all_preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_labels, all_preds, average="binary", pos_label=1, zero_division=0
    )
    cm = confusion_matrix(all_labels, all_preds)
    return {"accuracy": acc, "precision": precision, "recall": recall, "f1": f1, "confusion_matrix": cm.tolist()}


def log_run(args, metrics, elapsed_s):
    LOG_FILE.touch(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"\n## Run {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"- finetune: {args.finetune}\n")
        f.write(f"- epochs: {args.epochs}, batch_size: {args.batch_size}, lr: {args.lr}\n")
        f.write(f"- elapsed: {elapsed_s:.1f}s\n")
        f.write(f"- TEST accuracy: {metrics['accuracy']:.4f}\n")
        f.write(f"- TEST precision: {metrics['precision']:.4f}\n")
        f.write(f"- TEST recall: {metrics['recall']:.4f}\n")
        f.write(f"- TEST f1: {metrics['f1']:.4f}\n")
        f.write(f"- confusion_matrix [NORMAL,PNEUMONIA]: {metrics['confusion_matrix']}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--finetune", action="store_true")
    args = parser.parse_args()

    device = torch.device("cpu")
    print(f"Using device: {device}, finetune: {args.finetune}")

    train_set, val_set, test_set = load_datasets()
    print(f"Train: {len(train_set)}, Val: {len(val_set)}, Test: {len(test_set)}")

    train_loader, val_loader, test_loader = make_loaders(train_set, val_set, test_set, batch_size=args.batch_size)

    model = build_model(args.finetune).to(device)
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    n_total = sum(p.numel() for p in model.parameters())
    print(f"Trainable params: {n_trainable:,} / {n_total:,}")

    class_weights = compute_class_weights(train_set)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = Adam(trainable_params, lr=args.lr)

    best_f1 = 0.0
    CKPT_DIR.mkdir(exist_ok=True)
    ckpt_name = "resnet18_finetuned.pt" if args.finetune else "resnet18_baseline.pt"
    ckpt_path = CKPT_DIR / ckpt_name

    start = time.time()
    for epoch in range(args.epochs):
        model.train()
        running_loss = 0.0
        for images, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{args.epochs}"):
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * images.size(0)

        train_loss = running_loss / len(train_set)
        val_metrics = evaluate(model, val_loader)
        print(f"Epoch {epoch+1}: train_loss={train_loss:.4f} val_acc={val_metrics['accuracy']:.4f} val_f1={val_metrics['f1']:.4f}")

        if val_metrics["f1"] > best_f1:
            best_f1 = val_metrics["f1"]
            torch.save({"model_state_dict": model.state_dict(), "class_to_idx": {"NORMAL": 0, "PNEUMONIA": 1}}, ckpt_path)
            print(f"  -> new best (val_f1={best_f1:.4f}), saved to {ckpt_path}")

    elapsed = time.time() - start

    checkpoint = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_metrics = evaluate(model, test_loader)

    print("\n=== FINAL TEST METRICS ===")
    print(f"Accuracy:  {test_metrics['accuracy']:.4f}")
    print(f"Precision: {test_metrics['precision']:.4f}")
    print(f"Recall:    {test_metrics['recall']:.4f}")
    print(f"F1:        {test_metrics['f1']:.4f}")
    print(f"Confusion matrix [NORMAL,PNEUMONIA]: {test_metrics['confusion_matrix']}")
    print(f"\nCheckpoint saved: {ckpt_path}")

    log_run(args, test_metrics, elapsed)
    print(f"Logged to {LOG_FILE}")


if __name__ == "__main__":
    main()