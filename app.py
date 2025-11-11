from flask import Flask, request, jsonify
import pandas as pd
import random

# Import moduli locali con fallback automatico
try:
    from nutrition_ai import calcola_bmi
    from dispensa_ai import suggerisci_usi
    from coach import genera_messaggio
    from utils import match_ricette, genera_procedimento
except ImportError:
    # Fallback se i moduli non esistono ancora
    def calcola_bmi(peso, altezza, eta, sesso):
        bmi = round(peso / ((altezza / 100) ** 2), 1) if altezza > 0 else 0
        categoria = (
            "Sottopeso" if bmi < 18.5 else
            "Normopeso" if bmi < 25 else
            "Sovrappeso" if bmi < 30 else
            "Obesità"
        )
        return {"bmi": bmi, "categoria": categoria, "suggerimento": "Mantieni uno stile di vita equilibrato"}

    def suggerisci_usi(dispensa):
        return [f"Usa presto {item}" for item in dispensa]

    def genera_messaggio(bmi, dieta, trend):
        return f"Il tuo BMI è {bmi}. Continua con la dieta {dieta or 'bilanciata'}!"

    def match_ricette(recipes, dispensa, allergie, preferenze):
        base = [
            {"titolo": "Pasta al pomodoro", "ingredienti": ["pasta", "pomodoro", "olio"], "tempo": "15", "descrizione": "Classico primo piatto italiano"},
            {"titolo": "Insalata mista", "ingredienti": ["lattuga", "pomodoro", "olio"], "tempo": "10", "descrizione": "Fresca e leggera"}
        ]
        return base

    def genera_procedimento(titolo, ingredienti, dieta):
        return f"1️⃣ Prepara {', '.join(ingredienti)}.\n2️⃣ Segui la dieta {dieta or 'standard'}.\n3️⃣ Servi e gusta {titolo}!"

app = Flask(__name__)

# ===============================
# ENDPOINT DI TEST / STATUS
# ===============================
@app.route("/")
def home():
    return jsonify({
        "status": "AI online ✅",
        "message": "Flask is running correctly on Render",
        "routes": ["/ai/nutrizione", "/ai/ricetta", "/ai/procedimento", "/ai/coach", "/ai/dispensa"]
    })


# ===============================
# ENDPOINT RICETTE
# ===============================
@app.route("/ai/ricetta", methods=["POST"])
def ai_ricetta():
    """Suggerisce ricette in base alla dispensa e alle preferenze"""
    data = request.get_json(force=True)
    dispensa = set(i.lower() for i in data.get("dispensa", []))
    dieta = data.get("dieta", "")
    allergie = set(i.lower() for i in data.get("allergie", []))
    preferenze = set(i.lower() for i in data.get("preferenze", []))

    # Dataset di fallback
    recipes = pd.DataFrame([
        {"titolo": "Pasta al pomodoro", "ingredienti": "pasta,pomodoro,olio,basilico", "tempo": "15", "descrizione": "Classico primo piatto"},
        {"titolo": "Insalata mista", "ingredienti": "lattuga,pomodoro,olio,aceto", "tempo": "10", "descrizione": "Fresca e leggera"}
    ])

    risultati = match_ricette(recipes, dispensa, allergie, preferenze)
    return jsonify({"ricette": risultati[:5]})


# ===============================
# ENDPOINT PROCEDIMENTO
# ===============================
@app.route("/ai/procedimento", methods=["POST"])
def ai_procedimento():
    """Genera un procedimento testuale per una ricetta"""
    data = request.get_json(force=True)
    titolo = data.get("titolo", "Ricetta")
    ingredienti = data.get("ingredienti", [])
    dieta = data.get("dieta", "")
    testo = genera_procedimento(titolo, ingredienti, dieta)
    return jsonify({"procedimento": testo})


# ===============================
# ENDPOINT NUTRIZIONE
# ===============================
@app.route("/ai/nutrizione", methods=["POST"])
def ai_nutrizione():
    """Calcola BMI e profilo nutrizionale"""
    data = request.get_json(force=True)
    peso = float(data.get("peso", 0))
    altezza = float(data.get("altezza", 0))
    eta = int(data.get("eta", 0))
    sesso = data.get("sesso", "N/D")

    risultato = calcola_bmi(peso, altezza, eta, sesso)
    return jsonify(risultato)


# ===============================
# ENDPOINT DISPENSA
# ===============================
@app.route("/ai/dispensa", methods=["POST"])
def ai_dispensa():
    """Analizza la dispensa e suggerisce ingredienti da usare prima"""
    data = request.get_json(force=True)
    dispensa = data.get("dispensa", [])
    risultati = suggerisci_usi(dispensa)
    return jsonify({"alert": risultati})


# ===============================
# ENDPOINT COACH
# ===============================
@app.route("/ai/coach", methods=["POST"])
def ai_coach():
    """Genera un messaggio motivazionale"""
    data = request.get_json(force=True)
    bmi = data.get("bmi", 0)
    dieta = data.get("dieta", "")
    trend = data.get("trend_peso", "stabile")

    messaggio = genera_messaggio(bmi, dieta, trend)
    return jsonify({"coach_message": messaggio})


# ===============================
# RUN LOCALE
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
