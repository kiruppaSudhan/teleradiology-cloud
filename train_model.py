import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import numpy as np

IMG_SIZE = 224
BATCH_SIZE = 32
EPOCHS = 10
CLASSES = ['glioma', 'meningioma', 'notumor', 'pituitary']

# Data generators with augmentation
train_gen = ImageDataGenerator(
    rescale=1./255,
    rotation_range=15,
    horizontal_flip=True,
    zoom_range=0.1,
    validation_split=0.2
)

train_data = train_gen.flow_from_directory(
    'dataset/Training',
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='training'
)

val_data = train_gen.flow_from_directory(
    'dataset/Training',
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='validation'
)

# MobileNetV2 base (pretrained ImageNet weights)
base = MobileNetV2(weights='imagenet', include_top=False,
                   input_shape=(IMG_SIZE, IMG_SIZE, 3))
base.trainable = False  # freeze base

x = base.output
x = GlobalAveragePooling2D()(x)
x = Dropout(0.3)(x)
x = Dense(128, activation='relu')(x)
output = Dense(4, activation='softmax')(x)

model = Model(inputs=base.input, outputs=output)
model.compile(optimizer='adam',
              loss='categorical_crossentropy',
              metrics=['accuracy'])

# Train
history = model.fit(train_data, validation_data=val_data, epochs=EPOCHS)

# Evaluate on test set
test_gen = ImageDataGenerator(rescale=1./255)
test_data = test_gen.flow_from_directory(
    'dataset/Testing',
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode='categorical'
)
loss, acc = model.evaluate(test_data)
print(f"\n✅ Test Accuracy: {acc*100:.2f}%")

# Save
model.save('tumor_model.h5')
print("✅ Model saved as tumor_model.h5")
