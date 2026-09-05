import pandas as pd
import os
import argparse
from tqdm import tqdm
from PIL import Image

def audit_dataset(metadata_path, image_dirs):
    print("=====================================")
    print("      DATASET AUDIT REPORT           ")
    print("=====================================\n")
    
    if not os.path.exists(metadata_path):
        print(f"ERROR: Metadata file not found at {metadata_path}")
        return
        
    df = pd.read_csv(metadata_path)
    total_images = len(df)
    print(f"Total entries in metadata: {total_images}")
    
    # 1. Check for missing values in metadata (especially age, sex)
    print("\n--- Missing Values Check ---")
    null_counts = df.isnull().sum()
    print(null_counts[null_counts > 0])
    if 'age' in df.columns and df['age'].isnull().any():
        print("Note: 'age' column has missing values. Imputation may be required if using age as a feature.")
    if 'sex' in df.columns and df['sex'].isnull().any():
        print("Note: 'sex' column has missing values.")
        
    # 2. Class Balance
    print("\n--- Class Balance ---")
    if 'dx' in df.columns:
        class_counts = df['dx'].value_counts()
        class_pcts = df['dx'].value_counts(normalize=True) * 100
        balance_df = pd.DataFrame({'Count': class_counts, 'Percentage': class_pcts})
        print(balance_df)
        
        if 'nv' in class_pcts and class_pcts['nv'] > 60:
            print("\nWARNING: SEVERE CLASS IMBALANCE DETECTED!")
            print("The 'nv' (Melanocytic nevi) class constitutes ~67% of the dataset.")
            print("Ensure class weighting, focal loss, or stratified sampling is used during training to prevent the model from blindly predicting 'nv'.")
    else:
        print("Column 'dx' not found in metadata.")
        
    # 3. Leakage Risk: Unique lesion_ids vs total images
    print("\n--- Data Leakage Risk (Lesion ID) ---")
    if 'lesion_id' in df.columns:
        unique_lesions = df['lesion_id'].nunique()
        print(f"Total Images: {total_images}")
        print(f"Unique Lesions: {unique_lesions}")
        print(f"Images per Lesion (avg): {total_images / unique_lesions:.2f}")
        print("Observation: The same lesion appears multiple times (from different angles/zooms).")
        print("If a random split is used, the same lesion will leak across train/val/test splits.")
        print("-> This has been FIXED in preprocessing.py via GroupShuffleSplit on 'lesion_id'.")
    else:
        print("Column 'lesion_id' not found in metadata.")
        
    # 4. Check for missing/corrupt image files across both part folders
    print("\n--- Image File Verification ---")
    print(f"Searching across {len(image_dirs)} directories: {image_dirs}")
    
    missing_files = 0
    corrupt_files = 0
    
    for _, row in tqdm(df.iterrows(), total=total_images, desc="Verifying images"):
        img_id = row['image_id']
        found_path = None
        
        for d in image_dirs:
            potential_path = os.path.join(d, f"{img_id}.jpg")
            if os.path.exists(potential_path):
                found_path = potential_path
                break
                
        if found_path is None:
            missing_files += 1
        else:
            try:
                with Image.open(found_path) as img:
                    img.verify() # verify that it is, in fact, an image
            except Exception:
                corrupt_files += 1
                
    print("\nVerification Results:")
    print(f"Missing Files: {missing_files}")
    print(f"Corrupt Files: {corrupt_files}")
    
    if missing_files == 0 and corrupt_files == 0:
        print("All image files exist and are valid.")
    else:
        print("WARNING: Dataset is missing files or has corrupt files. Check extraction process.")
        
    print("\n=====================================")
    print("         AUDIT COMPLETE              ")
    print("=====================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=str, default="../data/raw/HAM10000_metadata.csv")
    parser.add_argument("--data_dir", type=str, nargs="+", default=["../data/raw/HAM10000_images_part_1", "../data/raw/HAM10000_images_part_2"])
    args = parser.parse_args()
    
    audit_dataset(args.metadata, args.data_dir)
