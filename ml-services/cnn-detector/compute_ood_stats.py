import os
import sys
import glob
import cv2
import numpy as np
import torch
import torch.nn as nn

# Add backend to sys.path to reuse its code exactly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))
from app.ai.models.pneumonia_cnn import load_pneumonia_model
from app.ai.inference.image_processing import preprocess_for_cnn

def get_penultimate_features(model, tensor_img):
    # ResNet18 forward pass up to avgpool
    x = model.conv1(tensor_img)
    x = model.bn1(x)
    x = model.relu(x)
    x = model.maxpool(x)

    x = model.layer1(x)
    x = model.layer2(x)
    x = model.layer3(x)
    x = model.layer4(x)

    x = model.avgpool(x)
    x = torch.flatten(x, 1)
    return x

def extract_features_from_dir(model, data_dir, device):
    features = []
    labels = []
    
    classes = ['NORMAL', 'PNEUMONIA']
    for label_idx, cls_name in enumerate(classes):
        cls_dir = os.path.join(data_dir, cls_name)
        if not os.path.isdir(cls_dir):
            continue
            
        filepaths = glob.glob(os.path.join(cls_dir, '*.*'))
        print(f"Extracting features for {cls_name} ({len(filepaths)} images)...")
        
        for fp in filepaths:
            # Same pipeline as backend
            img = cv2.imread(fp)
            if img is None:
                continue
                
            preprocessed = preprocess_for_cnn(img)[0] # get rid of batch dim for now
            # Convert (H, W, C) -> (C, H, W)
            image_transposed = np.transpose(preprocessed, (2, 0, 1))
            tensor_img = torch.tensor(image_transposed, dtype=torch.float32).unsqueeze(0).to(device)
            
            with torch.no_grad():
                feat = get_penultimate_features(model, tensor_img)
                features.append(feat.cpu().numpy()[0])
                labels.append(label_idx)
                
    return np.array(features), np.array(labels)

def main():
    device = "cpu"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ckpt_path = os.path.join(base_dir, 'checkpoints', 'resnet18_finetuned.pt')
    
    if not os.path.exists(ckpt_path):
        # Fallback to backend model if it doesn't exist in ml-services
        ckpt_path = os.path.abspath(os.path.join(base_dir, '../../backend/app/ai/models/pneumonia_cnn.pt'))
    
    print(f"Loading model from {ckpt_path}...")
    model = load_pneumonia_model(ckpt_path, device=device)
    model.eval()
    
    train_dir = os.path.join(base_dir, 'data', 'train')
    test_dir = os.path.join(base_dir, 'data', 'test')
    
    print("--- Processing Training Set ---")
    train_features, train_labels = extract_features_from_dir(model, train_dir, device)
    
    if len(train_features) == 0:
        print("No training data found!")
        return
        
    print(f"Extracted {len(train_features)} feature vectors of size {train_features.shape[1]}")
    
    # Compute Class Means
    mu_normal = np.mean(train_features[train_labels == 0], axis=0)
    mu_pneumonia = np.mean(train_features[train_labels == 1], axis=0)
    
    # Compute Tied Covariance Matrix
    # Center features by their respective class means
    centered_features = np.zeros_like(train_features)
    centered_features[train_labels == 0] = train_features[train_labels == 0] - mu_normal
    centered_features[train_labels == 1] = train_features[train_labels == 1] - mu_pneumonia
    
    # Covariance = (X^T * X) / (N - 1)
    # Using np.cov expects variables as rows, observations as columns, so we transpose
    cov_matrix = np.cov(centered_features, rowvar=False)
    
    # Add small epsilon to diagonal for numerical stability (regularization)
    epsilon = 1e-5
    cov_matrix += np.eye(cov_matrix.shape[0]) * epsilon
    
    # Inverse Covariance
    inv_cov_matrix = np.linalg.pinv(cov_matrix)
    
    print("Computed means and inverse covariance matrix.")
    
    # Compute distances for train set to see distribution
    def mahalanobis(f, mu, inv_cov):
        diff = f - mu
        return np.dot(np.dot(diff, inv_cov), diff.T)
        
    def get_min_dist(features):
        dists = []
        for f in features:
            d_norm = mahalanobis(f, mu_normal, inv_cov_matrix)
            d_pneu = mahalanobis(f, mu_pneumonia, inv_cov_matrix)
            dists.append(min(d_norm, d_pneu))
        return np.array(dists)
        
    train_dists = get_min_dist(train_features)
    print(f"Train Distances - Mean: {np.mean(train_dists):.2f}, 99th Pct: {np.percentile(train_dists, 99):.2f}, Max: {np.max(train_dists):.2f}")
    
    # Determine safe threshold using Test Set
    print("--- Processing Test Set ---")
    test_features, _ = extract_features_from_dir(model, test_dir, device)
    
    if len(test_features) > 0:
        test_dists = get_min_dist(test_features)
        print(f"Test Distances - Mean: {np.mean(test_dists):.2f}, 99th Pct: {np.percentile(test_dists, 99):.2f}, Max: {np.max(test_dists):.2f}")
        # A conservative threshold: slightly higher than max test distance, or 99th percentile + margin
        threshold = float(np.max(test_dists) * 1.5) 
    else:
        # Fallback if no test data
        threshold = float(np.percentile(train_dists, 99) * 2.0)
        
    print(f"--- Recommended OOD Threshold: {threshold:.2f} ---")
    
    # Save statistics
    out_path = os.path.join(base_dir, 'checkpoints', 'ood_stats.npz')
    np.savez(out_path, 
             mu_normal=mu_normal, 
             mu_pneumonia=mu_pneumonia, 
             inv_cov_matrix=inv_cov_matrix, 
             threshold=threshold)
             
    # Also copy to backend
    backend_out_path = os.path.abspath(os.path.join(base_dir, '../../backend/app/ai/models/ood_stats.npz'))
    np.savez(backend_out_path, 
             mu_normal=mu_normal, 
             mu_pneumonia=mu_pneumonia, 
             inv_cov_matrix=inv_cov_matrix, 
             threshold=threshold)
             
    print(f"Saved OOD statistics to {out_path} and {backend_out_path}")

if __name__ == "__main__":
    main()
