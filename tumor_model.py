import numpy as np
import os

_interpreter = None

def _get_interpreter():
    global _interpreter
    if _interpreter is None:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter

        model_path = os.path.join(os.path.dirname(__file__), "tumor_model.tflite")
        _interpreter = Interpreter(model_path=model_path)
        _interpreter.allocate_tensors()
        print("TFLite model loaded.")
    return _interpreter


def detect_tumor(arr: np.ndarray) -> str:
    try:
        interpreter = _get_interpreter()

        input_details  = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Check what shape the model actually expects
        expected_shape = input_details[0]['shape']  # e.g. (1, 224, 224, 1) or (1, 224, 224, 3)
        expected_channels = expected_shape[-1]

        img = arr.astype(np.float32)

        # Fix channels to match what model expects
        if img.ndim == 2:
            # Grayscale image
            if expected_channels == 3:
                img = np.stack([img, img, img], axis=-1)
            else:
                img = np.expand_dims(img, axis=-1)
        elif img.ndim == 3 and img.shape[-1] == 3:
            # RGB image
            if expected_channels == 1:
                # Convert RGB to grayscale
                img = np.mean(img, axis=-1, keepdims=True)
        
        img = np.expand_dims(img, axis=0)  # add batch dimension

        interpreter.set_tensor(input_details[0]['index'], img)
        interpreter.invoke()

        output = interpreter.get_tensor(output_details[0]['index'])
        
        # Handle both sigmoid (binary) and softmax (multi-class) outputs
        if output.shape[-1] == 1:
            score = float(output[0][0])
            return "Tumor Detected" if score > 0.5 else "No Tumor"
        else:
            # Multi-class: classes are typically [glioma, meningioma, no_tumor, pituitary]
            classes = ["Glioma", "Meningioma", "No Tumor", "Pituitary Tumor"]
            predicted = int(np.argmax(output[0]))
            confidence = float(np.max(output[0])) * 100
            label = classes[predicted] if predicted < len(classes) else f"Class {predicted}"
            return f"{label} ({confidence:.1f}% confidence)"

    except Exception as e:
        print("Tumor detection error:", e)
        return f"Detection failed: {str(e)}"
