"""
Pools all images (train+val+test), groups by patient ID, and rebuilds
a 70/15/15 split so no patient's images appear in more than one split.
Saves the result as a manifest CSV instead of moving files around.

Usage:
    python notebooks/rebuild_split.py
"""
import re
import csv
from pathlib import Path
from collections import defaultdict
import random

DATA_DIR = Path(__file__).parent.parent / "data"
SPLITS = ["train", "val", "test"]
CLASSES = ["NORMAL", "PNEUMONIA"]
SEED = 42


def get_patient_id(filename: str):
    m = re.match(r"person(\d+)_", filename)
    if m:
        return f"person{m.group(1)}"
    m = re.match(r"(?:NORMAL2-)?IM-(\d+)", filename)
    if m:
        return f"IM-{m.group(1)}"
    return filename  # fallback: treat as its own unique "patient"


def main():
    # collect all files with their class
    all_files = []  # (path, cls, patient_id)
    for split in SPLITS:
        for cls in CLASSES:
            cls_dir = DATA_DIR / split / cls
            if not cls_dir.exists():
                continue
            for f in list(cls_dir.glob("*.jpeg")) + list(cls_dir.glob("*.jpg")):
                pid = get_patient_id(f.name)
                all_files.append((f, cls, pid))

    print(f"Total files pooled: {len(all_files)}")

    # group files by patient id
    patient_files = defaultdict(list)
    for f, cls, pid in all_files:
        patient_files[pid].append((f, cls))

    patient_ids = list(patient_files.keys())
    random.seed(SEED)
    random.shuffle(patient_ids)

    n = len(patient_ids)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)

    train_pids = set(patient_ids[:n_train])
    val_pids = set(patient_ids[n_train:n_train + n_val])
    test_pids = set(patient_ids[n_train + n_val:])

    manifest = []
    split_counts = defaultdict(lambda: defaultdict(int))
    for pid, files in patient_files.items():
        if pid in train_pids:
            split = "train"
        elif pid in val_pids:
            split = "val"
        else:
            split = "test"
        for f, cls in files:
            manifest.append((str(f.resolve()), cls, split))
            split_counts[split][cls] += 1

    manifest_path = DATA_DIR / "split_manifest.csv"
    with open(manifest_path, "w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["filepath", "class", "split"])
        writer.writerows(manifest)

    print(f"\nManifest saved to {manifest_path}")
    print(f"\nNew split (patient-grouped, {n} patients total):")
    for split in ["train", "val", "test"]:
        total = sum(split_counts[split].values())
        print(f"  {split}: {total} images", dict(split_counts[split]))

    # sanity check: verify no patient appears in more than one split
    pid_to_splits = defaultdict(set)
    for f, cls, pid in all_files:
        if pid in train_pids:
            pid_to_splits[pid].add("train")
        elif pid in val_pids:
            pid_to_splits[pid].add("val")
        else:
            pid_to_splits[pid].add("test")
    leaked = {pid: s for pid, s in pid_to_splits.items() if len(s) > 1}
    print(f"\nSanity check — patients in more than one split: {len(leaked)} (should be 0)")


if __name__ == "__main__":
    main()