"""
Run this BEFORE training. Checks:
  - class balance per split
  - corrupt/unreadable images
  - image resolution range
  - exact-duplicate images (via MD5 hash)
  - patient-level leakage across splits (critical check)

Usage:
    python notebooks/audit_dataset.py
"""
import hashlib
from pathlib import Path
from collections import defaultdict
import re
from PIL import Image

DATA_DIR = Path(__file__).parent.parent / "data"
SPLITS = ["train", "val", "test"]
CLASSES = ["NORMAL", "PNEUMONIA"]


def get_patient_id(filename: str):
    """PNEUMONIA files: personNNNN_...  NORMAL files: IM-NNNN... or NORMAL2-IM-NNNN..."""
    m = re.match(r"person(\d+)_", filename)
    if m:
        return f"person{m.group(1)}"
    m = re.match(r"(?:NORMAL2-)?IM-(\d+)", filename)
    if m:
        return f"IM-{m.group(1)}"
    return None


def audit():
    if not DATA_DIR.exists():
        print(f"ERROR: {DATA_DIR} not found.")
        return

    counts = defaultdict(dict)
    all_files = []          # (split, cls, path)
    hashes = defaultdict(list)   # md5 -> [(split, path), ...]
    patient_splits = defaultdict(set)  # patient_id -> {splits it appears in}
    unparsed = 0
    corrupt = []
    widths, heights = [], []

    for split in SPLITS:
        split_dir = DATA_DIR / split
        if not split_dir.exists():
            print(f"WARNING: {split_dir} missing")
            continue
        for cls in CLASSES:
            cls_dir = split_dir / cls
            if not cls_dir.exists():
                continue
            files = list(cls_dir.glob("*.jpeg")) + list(cls_dir.glob("*.jpg"))
            counts[split][cls] = len(files)
            for f in files:
                all_files.append((split, cls, f))

    print("=" * 55)
    print("DATASET AUDIT REPORT")
    print("=" * 55)

    for split in SPLITS:
        if split not in counts:
            continue
        total = sum(counts[split].values())
        print(f"\n{split.upper()} (total: {total})")
        for cls in CLASSES:
            n = counts[split].get(cls, 0)
            pct = (n / total * 100) if total else 0
            print(f"  {cls}: {n} ({pct:.1f}%)")

    print(f"\nScanning {len(all_files)} files (hash + resolution + corruption + patient ID)...")
    for split, cls, f in all_files:
        try:
            with Image.open(f) as img:
                img.verify()
            with Image.open(f) as img:
                widths.append(img.size[0])
                heights.append(img.size[1])
        except Exception as e:
            corrupt.append((str(f), str(e)))
            continue

        md5 = hashlib.md5(f.read_bytes()).hexdigest()
        hashes[md5].append((split, f))

        pid = get_patient_id(f.name)
        if pid is None:
            unparsed += 1
        else:
            patient_splits[pid].add(split)

    print(f"\nCorrupt/unreadable files: {len(corrupt)}")
    for path, err in corrupt[:10]:
        print(f"  {path}: {err}")

    if widths:
        print(f"\nResolution range: {min(widths)}x{min(heights)} to {max(widths)}x{max(heights)}")

    dup_groups = {h: v for h, v in hashes.items() if len(v) > 1}
    cross_split_dups = {h: v for h, v in dup_groups.items() if len({s for s, _ in v}) > 1}
    print(f"\nExact-duplicate groups (same image, different filename): {len(dup_groups)}")
    print(f"  Of these, groups spanning MORE THAN ONE SPLIT (real leakage risk): {len(cross_split_dups)}")
    for h, v in list(cross_split_dups.items())[:5]:
        print(f"    {[str(p) for s, p in v]}")

    print(f"\nFilenames that didn't match expected patient-ID pattern: {unparsed}")
    leaked = {pid: splits for pid, splits in patient_splits.items() if len(splits) > 1}
    print(f"Patient IDs appearing in MORE THAN ONE SPLIT: {len(leaked)}")
    if leaked:
        print("  >> CRITICAL: patient-level leakage confirmed. Do NOT train on this split as-is.")
        print("  Example leaked patients:", list(leaked.items())[:5])
    else:
        print("  No cross-split patient leakage detected by filename pattern.")

    print("\nDone.")


if __name__ == "__main__":
    audit()