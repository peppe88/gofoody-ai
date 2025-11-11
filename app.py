from flask import Flask, request, jsonify
import pandas as pd
import random
from nutrition_ai import calcola_bmi
from dispensa_ai import suggerisci_usi
from coach import genera_messaggio
from utils import match_ricette, genera_procedimento

app = Flask(__name__)

# Carica il dataset di ricette
try:
    recipes = pd.read_csv("recipes.csv")
except FileNotFoundError:
    recipes = pd.DataFrame([
        {
            "titolo": "Pasta al pomodoro",
            "ingredienti": "pasta,pomodoro,olio,basilico",
            "tempo": "15",
            "descrizione": "Classico primo semplice e gustoso"
        },
        {
            "titolo": "Insalata mista",
            "ingredienti": "lattuga,pomodoro,olio,aceto",
            "tempo": "10",
            "descrizione": "Fresca e leggera per ogni pasto"
        }
    ])

# --- ENDPOINT RICETTE ---
@app.route("/ai/ricetta", methods=["POST"])
def ai_ricetta():
    """Suggerisce ricette in base alla dispensa e alle preferenze"""
    data = request.get_json()
    dispensa = set(i.lower() for i in data.get("dispensa", []))
    dieta = data.get("dieta", "")
    allergie = set(i.lower() for i in data.get("allergie", []))
    preferenze = set(i.lower() for i in data.get("preferenze", []))

    risultati = match_ricette(recipes, dispensa, allergie, preferenze)
    return jsonify({"ricette": risultati[:5]})


# --- ENDPOINT PROCEDIMENTO ---
@app.route("/ai/procedimento", methods=["POST"])
def ai_procedimento():
    """Genera un procedimento testuale per una ricetta"""
    data = request.get_json()
    titolo = data.get("titolo", "Ricetta")
    ingredienti = data.get("ingredienti", [])
    dieta = data.get("dieta", "")
    testo = genera_procedimento(titolo, ingredienti, dieta)
    return jsonify({"procedimento": testo})


# --- ENDPOINT NUTRIZIONE ---
@app.route("/ai/nutrizione", methods=["POST"])
def ai_nutrizione():
    """Calcola BMI e profilo nutrizionale"""
    data = request.get_json()
    peso = float(data.get("peso", 0))
    altezza = float(data.get("altezza", 0))
    eta = int(data.get("eta", 0))
    sesso = data.get("sesso", "N/D")

    risultato = calcola_bmi(peso, altezza, eta, sesso)
    return jsonify(risultato)


# --- ENDPOINT DISPENSA ---
@app.route("/ai/dispensa", methods=["POST"])
def ai_dispensa():
    """Analizza la dispensa e suggerisce ingredienti da usare prima"""
    data = request.get_json()
    dispensa = data.get("dispensa", [])
    risultati = suggerisci_usi(dispensa)
    return jsonify({"alert": risultati})


# --- ENDPOINT COACH ---
@app.route("/ai/coach", methods=["POST"])
def ai_coach():
    """Genera un messaggio motivazionale"""
    data = request.get_json()
    bmi = data.get("bmi", 0)
    dieta = data.get("dieta", "")
    trend = data.get("trend_peso", "stabile")

    messaggio = genera_messaggio(bmi, dieta, trend)
    return jsonify({"coach_message": messaggio})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)