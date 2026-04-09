import numpy as np
from tensorflow.keras.models import load_model
from PIL import Image
import io

CLASSES = ['Glioma Tumor', 'Meningioma Tumor', 'No Tumor', 'Pituitary Tumor']
_model = None

def get_model():
    global _model
    if _model is None:
        _model = load_model('tumor_model.h5')
    return _model

def detect_tumor(arr):
    """
    arr: numpy array of shape (224,224) or (224,224,3), values 0-1
    Returns: string like "Glioma Tumor (94.2% confidence)"
    """
    try:
        model = get_model()
        
        # Ensure RGB (3 channels)
        if len(arr.shape) == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        elif arr.shape[-1] == 1:
            arr = np.concatenate([arr, arr, arr], axis=-1)
        
        # Resize to 224x224 if needed
        if arr.shape[:2] != (224, 224):
            img = Image.fromarray((arr * 255).astype(np.uint8))
            img = img.resize((224, 224))
            arr = np.array(img) / 255.0
        
        # Predict
        inp = np.expand_dims(arr, axis=0)  # (1, 224, 224, 3)
        preds = model.predict(inp, verbose=0)[0]
        
        idx = np.argmax(preds)
        label = CLASSES[idx]
        confidence = preds[idx] * 100
        
        return f"{label} ({confidence:.1f}% confidence)"
    
    except Exception as e:
        return f"Detection error: {str(e)}"
