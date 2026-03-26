import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

# Load dataset
data = pd.read_csv("diabetes.csv")

# Features and target
X = data[["Glucose", "BMI", "Age"]]
y = data["Outcome"]

# Train model
model = LogisticRegression()
model.fit(X, y)

# Prediction function
def predict_diabetes(glucose, bmi, age):
    prediction = model.predict([[glucose, bmi, age]])
    return "Diabetic" if prediction[0] == 1 else "Non-Diabetic"
