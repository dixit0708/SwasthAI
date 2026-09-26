
## DermNet ResNet50 Fine-Tuning (Colab GPU) - CONTINUATION RUN
- **Total Epochs Budget:** 40
- **Final Best Macro F1:** 0.6546
- **Additions:** Early Stopping (patience=5), ReduceLROnPlateau

### Best Epoch Classification Report
```text
                                                                    precision    recall  f1-score   support

                                           Acne and Rosacea Photos       0.82      0.82      0.82       231
Actinic Keratosis Basal Cell Carcinoma and other Malignant Lesions       0.74      0.69      0.71       288
                                          Atopic Dermatitis Photos       0.60      0.68      0.64       123
                                            Bullous Disease Photos       0.73      0.58      0.65       113
                Cellulitis Impetigo and other Bacterial Infections       0.57      0.36      0.44        73
                                                     Eczema Photos       0.58      0.66      0.62       307
                                      Exanthems and Drug Eruptions       0.56      0.49      0.52       103
                 Hair Loss Photos Alopecia and other Hair Diseases       0.65      0.75      0.70        60
                                  Herpes HPV and other STDs Photos       0.67      0.63      0.65       102
                      Light Diseases and Disorders of Pigmentation       0.61      0.56      0.58       144
                        Lupus and other Connective Tissue diseases       0.46      0.50      0.48       105
                               Melanoma Skin Cancer Nevi and Moles       0.75      0.68      0.71       117
                                Nail Fungus and other Nail Disease       0.86      0.80      0.83       260
                    Poison Ivy Photos and other Contact Dermatitis       0.68      0.43      0.53        65
             Psoriasis pictures Lichen Planus and related diseases       0.58      0.66      0.62       345
             Scabies Lyme Disease and other Infestations and Bites       0.65      0.57      0.61       108
                      Seborrheic Keratoses and other Benign Tumors       0.71      0.78      0.74       343
                                                  Systemic Disease       0.64      0.58      0.61       152
            Tinea Ringworm Candidiasis and other Fungal Infections       0.63      0.72      0.67       327
                                                   Urticaria Hives       0.86      0.72      0.78        53
                                                   Vascular Tumors       0.77      0.74      0.75       121
                                                 Vasculitis Photos       0.76      0.63      0.69       104
                        Warts Molluscum and other Viral Infections       0.70      0.71      0.71       269

                                                          accuracy                           0.67      3913
                                                         macro avg       0.68      0.64      0.65      3913
                                                      weighted avg       0.68      0.67      0.67      3913

```

## Out-of-Distribution (OOD) Calibration (Mahalanobis)
To prevent the model from misclassifying random real-world photos (like uncropped selfies or non-skin photos), we calibrated a Mahalanobis distance OOD detector:
- **Features**: ResNet50 penultimate features (2048 dimensions).
- **In-Distribution Test Max Distance**: 2,406,097
- **Selected Threshold**: 3,500,000

Any image resulting in a minimum Mahalanobis distance across the 23 classes that is greater than 3,500,000 will be rejected by the API as OOD.

### Out-of-Distribution (OOD) Calibration Journey
**Initial Attempt: Mahalanobis Distance (Penultimate Features)**
- **Methodology**: Extracted 2048D ResNet50 features, computed class-conditional means, and a tied covariance matrix (regularized and properly conditioned using the full ~15.5k image training set where $n > d$).
- **Result**: Failed to clearly separate In-Distribution (ID) skin images from Out-of-Distribution (OOD) random images.
- **Why it failed**: The high diversity of the 23 skin classes creates a naturally wide, spread-out ID region. Many random, non-skin images map to "bland" features near the origin or overall mean in this 2048D space. As a result, OOD images frequently produced *lower* Mahalanobis distances (e.g., mean ~4700) than hard ID examples containing extreme medical features (e.g., ID max ~12000). Setting a threshold to accept 99% of ID images would blindly accept almost all OOD images.

**Final Approach: Ensemble Softmax Signal (Max Confidence + Entropy)**
- **Methodology**: Given the feature-space overlap, we fallback to a simpler, robust softmax-based ensemble.
- **Metric 1 (Max Softmax Confidence)**: Reject if the top predicted class confidence is below a threshold.
- **Metric 2 (Prediction Entropy)**: Reject if the entropy across all 23 classes exceeds a threshold (since a real image concentrates probability on 1-2 classes, whereas an unrelated OOD image smears probability thinly across many classes).
- **Limitation**: Softmax-based methods can sometimes be "confidently wrong" on OOD inputs, but this ensemble avoids the severe feature-space overlap seen with Mahalanobis in highly diverse classification tasks, providing a much cleaner separation.

### Domain Shift Mitigation: Heavy Data Augmentation
**Problem**: The model performs well on clinical DermNet images but fails on real-world smartphone photos (e.g., misclassifying acne due to different lighting, blur, and cropping).
**Solution**: Replaced the mild `get_train_transforms()` with a heavy augmentation pipeline to simulate smartphone artifacts.
- **Augmentations Added**: 
  - `RandomResizedCrop(scale=(0.5, 1.0))` (zooming/cropping)
  - `ColorJitter(0.4, 0.4, 0.4, 0.1)` (flash, varying indoor/outdoor light)
  - `RandomPerspective` (bad camera angles)
  - `GaussianBlur` (out-of-focus shots)
  - `RandomAdjustSharpness` (phone post-processing artifacts)
**Next Steps**: Retrain the model on Colab using these new robust transforms.
