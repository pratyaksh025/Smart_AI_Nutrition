import cv2
import numpy as np
from tensorflow.keras.models import load_model

model = load_model("models/cnn_model.h5")  # Load your trained food model

def preprocess_image(img_path):
    img = cv2.imread(img_path)
    img = cv2.resize(img, (128, 128))
    img = img / 255.0
    return np.expand_dims(img, axis=0)

def classify_food(img_path):
    img = preprocess_image(img_path)
    prediction = model.predict(img)
    return np.argmax(prediction)
