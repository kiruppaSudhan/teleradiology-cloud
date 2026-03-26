import numpy as np
from tensorflow.keras.models import load_model

# Load trained model
model = load_model("tumor_model.h5")

# Class labels (same order as dataset folders)
labels = ["glioma", "meningioma", "notumor", "pituitary"]

def detect_tumor(img_array):
    # reshape to match model input
    img = img_array.reshape(1, 128, 128, 1)

    # prediction
    prediction = model.predict(img)

    # get class
    result = labels[np.argmax(prediction)]

    return result
