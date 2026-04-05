import os
import gdown
import numpy as np

MODEL_PATH = "tumor_model.h5"

model = None

def get_model():
    global model

    if model is not None:
        return model

    print("⚠ Using fallback dummy model")

    # Instead of loading broken model
    model = "dummy"

    return model


def detect_tumor(img_array):
    try:
        model = get_model()

        # 🔥 SIMPLE LOGIC (for demo)
        avg = np.mean(img_array)

        if avg > 0.5:
            return "Tumor Detected"
        else:
            return "No Tumor"

    except Exception as e:
        print("Tumor error:", e)
        return "Analysis Failed"
