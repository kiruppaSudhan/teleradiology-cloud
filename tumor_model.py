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

model = None

def get_model():
    global model
    if model is None:
        download_model()
        model = load_model(MODEL_PATH)
    return model

def detect_tumor(img):
    model = get_model()
    
    # YOUR EXISTING PREPROCESSING HERE
    # Example:
    # img = preprocess(img)
    
    prediction = model.predict(img)
    
    return prediction
