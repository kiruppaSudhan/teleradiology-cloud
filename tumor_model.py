import numpy as np
import os

# ── Lazy-load: model is loaded once on first request, NOT at import time ──
_interpreter = None

def _get_interpreter():
    global _interpreter
    if _interpreter is None:
        try:
            # Try tflite-runtime first (lightest, recommended for Render)
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            # Fall back to TFLite from full tensorflow if tflite-runtime not installed
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter

        model_path = os.path.join(os.path.dirname(__file__), "tumor_model.tflite")
        _interpreter = Interpreter(model_path=model_path)
        _interpreter.allocate_tensors()
        print("TFLite model loaded.")
    return _interpreter


def detect_tumor(arr: np.ndarray) -> str:
    """
    arr: float32 numpy array of shape (224, 224, 3), values in [0, 1]
    Returns: 'Tumor Detected' | 'No Tumor' | error string
    """
    try:
        interpreter = _get_interpreter()

        input_details  = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Prepare input tensor
        img = arr.astype(np.float32)
        if img.ndim == 2:                        # grayscale → RGB
            img = np.stack([img, img, img], axis=-1)
        img = np.expand_dims(img, axis=0)        # (1, 224, 224, 3)

        interpreter.set_tensor(input_details[0]['index'], img)
        interpreter.invoke()

        output = interpreter.get_tensor(output_details[0]['index'])
        score  = float(output[0][0])             # sigmoid output

        return "Tumor Detected" if score > 0.5 else "No Tumor"

    except Exception as e:
        print("Tumor detection error:", e)
        return f"Detection failed: {str(e)}"
