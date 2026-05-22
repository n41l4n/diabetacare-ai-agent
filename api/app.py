from fastapi import FastAPI
from pydantic import BaseModel, Field
import pandas as pd
import joblib
from pathlib import Path


# =========================
# Load model
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model" / "diabetes_model.pkl"
FEATURES_PATH = BASE_DIR / "model" / "selected_features.pkl"

model = joblib.load(MODEL_PATH)
selected_features = joblib.load(FEATURES_PATH)


# =========================
# Create FastAPI app
# =========================

app = FastAPI(
    title="Diabetes Risk Prediction API",
    description="API untuk screening awal risiko diabetes menggunakan model Random Forest.",
    version="1.0.0"
)


# =========================
# Input schema
# =========================

class DiabetesInput(BaseModel):
    HighBP: int = Field(..., description="0 = tidak punya tekanan darah tinggi, 1 = punya tekanan darah tinggi")
    HighChol: int = Field(..., description="0 = kolesterol tidak tinggi, 1 = kolesterol tinggi")
    BMI: float = Field(..., description="Body Mass Index")
    Smoker: int = Field(..., description="0 = tidak pernah merokok, 1 = pernah merokok")
    PhysActivity: int = Field(..., description="0 = tidak aktif fisik, 1 = aktif fisik")
    Fruits: int = Field(..., description="0 = jarang konsumsi buah, 1 = konsumsi buah")
    Veggies: int = Field(..., description="0 = jarang konsumsi sayur, 1 = konsumsi sayur")
    GenHlth: int = Field(..., description="General health: 1 = excellent, 5 = poor")
    MentHlth: int = Field(..., description="Jumlah hari kondisi mental tidak baik dalam 30 hari terakhir")
    PhysHlth: int = Field(..., description="Jumlah hari kondisi fisik tidak baik dalam 30 hari terakhir")
    Age: int = Field(..., description="Kategori usia dari dataset")
    Sex: int = Field(..., description="0 = female, 1 = male")


# =========================
# Helper functions
# =========================

def get_risk_level(probability: float) -> str:
    if probability < 0.35:
        return "Low"
    elif probability < 0.65:
        return "Moderate"
    else:
        return "High"


def get_contributing_factors(data: DiabetesInput) -> list[str]:
    factors = []

    if data.HighBP == 1:
        factors.append("tekanan darah tinggi")
    if data.HighChol == 1:
        factors.append("kolesterol tinggi")
    if data.BMI >= 30:
        factors.append("BMI berada pada kategori obesitas")
    elif data.BMI >= 25:
        factors.append("BMI berada pada kategori overweight")
    if data.Smoker == 1:
        factors.append("riwayat merokok")
    if data.PhysActivity == 0:
        factors.append("kurangnya aktivitas fisik")
    if data.Fruits == 0:
        factors.append("konsumsi buah yang rendah")
    if data.Veggies == 0:
        factors.append("konsumsi sayur yang rendah")
    if data.GenHlth >= 4:
        factors.append("persepsi kesehatan umum yang kurang baik")
    if data.PhysHlth >= 10:
        factors.append("cukup banyak hari dengan kondisi fisik tidak baik")

    return factors


# =========================
# Routes
# =========================

@app.get("/")
def home():
    return {
        "message": "Diabetes Risk Prediction API is running.",
        "docs": "/docs"
    }


@app.post("/predict")
def predict_diabetes(data: DiabetesInput):
    input_dict = data.model_dump()

    input_df = pd.DataFrame([input_dict])
    input_df = input_df[selected_features]

    prediction = int(model.predict(input_df)[0])
    probability = float(model.predict_proba(input_df)[0][1])
    risk_level = get_risk_level(probability)
    contributing_factors = get_contributing_factors(data)

    return {
        "prediction": prediction,
        "diabetes_probability": round(probability, 3),
        "risk_level": risk_level,
        "contributing_factors": contributing_factors,
        "disclaimer": "Hasil ini hanya screening awal dan bukan diagnosis medis."
    }