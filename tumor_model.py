import os
import gdown
from tensorflow.keras.models import load_model

MODEL_PATH = "tumor_model.h5"
FILE_ID = "1beRY6Pho2Rd_obnlxpL1oJTq3wKmm4iW"

def download_model():
    if not os.path.exists(MODEL_PATH):
        url = f"https://drive.google.com/uc?id={FILE_ID}"
        print("Downloading model...")
        gdown.download(url, MODEL_PATH, quiet=False)

print("Initializing model...")

download_model()   # 🔥 DOWNLOAD AT STARTUP
model = load_model(MODEL_PATH)   # 🔥 LOAD AT STARTUP

print("Model loaded successfully!")

def detect_tumor(img):
    prediction = model.predict(img)
    return prediction
