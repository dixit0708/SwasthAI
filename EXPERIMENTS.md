# AI Models and Experiments

## Pneumonia Out-Of-Distribution (OOD) Detection

To prevent the Pneumonia CNN (ResNet18) from providing confident misdiagnoses on non-X-ray images, we employ a dual-signal ensemble OOD detection approach.

### The Problem
During evaluation, it was discovered that purely noise-based images (like a pure black square) or extremely dark, low-light photos could sometimes map to features deep inside the network that technically resemble "Pneumonia", returning high-confidence false positives.

### The Ensemble Solution
To solve this, we combine two distinct heuristics. An image is rejected if **either** heuristic flags it as OOD:

1. **Mahalanobis Distance (`MAHALANOBIS_THRESHOLD = 2000.0`)**
   - **How it works:** We extract the 512-dimensional output of the penultimate layer (Average Pooling) of ResNet18. We compute the Mahalanobis distance between this feature vector and the class-conditional mean vectors of the training set (`ood_stats.npz`), using a shared inverse covariance matrix.
   - **Why 2000.0?** Real X-rays from our test set produced distances up to ~1581. However, random images and real-world non-X-ray photos (e.g., LFW faces) produce distances significantly higher (often >3500). 2000.0 provides a safe buffer for legitimate medical edge cases while strictly cutting out foreign distributions.

2. **HSV Mean Saturation (`SATURATION_THRESHOLD = 100.0`)**
   - **How it works:** We convert the original BGR image to HSV and compute the mean of the Saturation channel.
   - **Why 100.0?** Genuine digital X-rays are perfectly grayscale (saturation = 0). A photo of a physical X-ray film might have some color tint (e.g. blueish), leading to a saturation around 80. However, most everyday non-medical color photos and objects have average saturations well over 100. This heuristic serves as a weak but fast structural filter.

### Future Improvements
While this ensemble drastically reduces false predictions on arbitrary uploads, it remains a set of heuristics. A more robust future improvement would be training a small, dedicated binary classifier (e.g., MobileNet) specifically on a dataset of `[Chest X-Rays]` vs. `[Diverse Non-X-Ray Images]` to act as a dedicated gatekeeper before the main CNN.
