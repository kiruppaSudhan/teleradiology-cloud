import cv2
import numpy as np

def detect_tumor(image_array):

    # normalize
    img = (image_array - image_array.min()) / (image_array.max() - image_array.min())

    # convert to 0-255
    img = (img * 255).astype(np.uint8)

    # blur to remove noise
    img_blur = cv2.GaussianBlur(img, (5,5), 0)

    # threshold (bright tumor areas)
    _, thresh = cv2.threshold(img_blur, 180, 255, cv2.THRESH_BINARY)

    # find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) > 2:
        return "Tumor Detected"
    else:
        return "No Tumor"
