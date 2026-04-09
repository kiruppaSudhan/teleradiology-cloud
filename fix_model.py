import tensorflow as tf

print("⚡ Loading model safely...")

model = tf.keras.models.load_model(
    "tumor_model.h5",
    compile=False
)

print("⚡ Cloning model (fixing compatibility)...")

new_model = tf.keras.models.clone_model(model)
new_model.set_weights(model.get_weights())

print("⚡ Saving fixed model...")

new_model.save("fixed_model.h5")

print("✅ DONE — Model fixed successfully")
