from tensorflow.keras.models import load_model

print("Loading old model...")
model = load_model("tumor_model.h5", compile=False)

print("Saving fixed model...")
model.save("tumor_model_fixed.h5")

print("Done ✅")
