import os
import gdown
import numpy as np

MODEL_PATH = "tumor_model.h5"

# 🔽 Download model if not present
def download_model():
    if not os.path.exists(MODEL_PATH):
        print("Downloading tumor model...")
        url = "https://drive.google.com/uc?id=1beRY6Pho2Rd_obnlxpL1oJTq3wKmm4iW"
        gdown.download(url, MODEL_PATH, quiet=False)

model = None

def get_model():
    global model

    if model is None:
        from tensorflow.keras.models import load_model
        model = load_model(MODEL_PATH)

    return model

def detect_tumor(img):
    model = get_model()

    pred = model.predict(img)

    prob = float(pred[0][0])

    if prob > 0.5:
        return f"Tumor Detected ({prob:.2f})"
    else:
        return f"No Tumor ({1 - prob:.2f})"
