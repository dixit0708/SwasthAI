# Pneumonia Chest X-Ray Dataset

This directory is intended to house the dataset for training the Pneumonia CNN detector. 

**Note: The actual dataset images are excluded from version control to prevent bloating the Git repository.**

## How to get the dataset
We use the **Chest X-Ray Images (Pneumonia)** dataset by Paul Mooney from Kaggle.
1. Download the dataset from: [https://www.kaggle.com/paultimothymooney/chest-xray-pneumonia](https://www.kaggle.com/paultimothymooney/chest-xray-pneumonia)
2. Extract the archive.
3. Place the `train`, `val`, and `test` folders directly inside this `data/` directory.

## Expected Directory Structure
```text
ml-services/cnn-detector/data/
├── README.md
├── train/
│   ├── NORMAL/
│   └── PNEUMONIA/
├── val/
│   ├── NORMAL/
│   └── PNEUMONIA/
└── test/
    ├── NORMAL/
    └── PNEUMONIA/
```

After placing the data here, you can run the `preprocessing.py` or `train.py` scripts from the parent directory.
