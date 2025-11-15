import os
import json
from flask import request, jsonify
from datetime import datetime

# ===========================
# CONFIG SICUREZZA
# ===========================
AI_KEY = os.getenv("AI_KEY", "gofoody_3f8G7pLzR!x2N9tQ@uY5aWsE#jD6kHrV^m1ZbTqL4cP0oFi")


def verifica_chiave():
    """Verifica che la richiesta contenga la chiave API corretta."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ")[1]
    return token == AI_KEY


# ===============================================
# CARICAMENTO DATABASE NUTRIZIONALE (300 alimenti)
# ===============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NUTRIENTS_PATH = os.path.join(BASE_DIR, "data", "nutrients.json")

try:
    with open(NUTRIENTS_PATH, "r", encoding="utf-8") as f:
        NUTRIENT_DB = json.load(f)
    if not isinstance(NUTRIENT_DB, list):
        NUTRIENT_DB = []
    print("✅ nutrients.json caricato (300 alimenti)")
except Exception as e:
    print("❌ Errore caricamento nutrients.json:", e)
    NUTRIENT_DB = []


# ===============================================
# FUNZIONI DI NORMALIZZAZIONE
# ===============================================
def normalizza_nome(nome):
    nome = nome.lower().strip()
    # sinonimi base come API
    mapping = {
        "pomodori": "pomodoro",
        "pomodorini": "pomodoro",
        "datterini": "pomodoro",
        "ciliegino": "pomodoro",
        "ciliegini": "pomodoro",
        "banane": "banana",
        "mele": "mela",
        "arance": "arancia",
        "zucchine": "zucchina"
    }
    return mapping.get(nome, nome)


# ===============================================
# FUNZIONE: CERCA NUTRIENTI PER ALIMENTO
# ===============================================
def trova_nutrienti(alimento_norm):
    """
    Cerca il valore nutrizionale in nutrients.json
    (kcal, carb, proteine, grassi per 100g)
    """
    alimento_norm = alimento_norm.lower().strip()

    for row in NUTRIENT_DB:
        nome = row.get("nome", "").lower()
        if alimento_norm == nome:
            return row

    # fuzzy fallback: contiene
    for row in NUTRIENT_DB:
        nome = row.get("nome", "").lower()
        if alimento_norm in nome or nome in alimento_norm:
            return row

    return None


# ===============================================
# FUNZIONE: CALCOLA KCAL DATI ALIMENTO + GRAMMI
# ===============================================
def calcola_kcal_da_nutrienti(alimento, quantita_g):
    nutr = trova_nutrienti(alimento)
    if not nutr:
        return None  # l’AI principale gestirà fallback

    kcal100 = float(nutr.get("kcal_100g", 0))
    return round((kcal100 * quantita_g) / 100.0, 1)


# ===============================================
# FUNZIONE PRINCIPALE BMI
# ===============================================
def calcola_bmi(peso, altezza, eta, sesso):
    """Calcola il BMI e restituisce valutazione e consiglio."""

    if altezza <= 0 or peso <= 0:
        return {
            "bmi": None,
            "categoria": "Dati non validi",
            "suggerimento": "Inserisci peso e altezza."
        }

    altezza_m = altezza / 100
    bmi = round(peso / (altezza_m ** 2), 1)

    # Classificazione OMS
    if bmi < 18.5:
        categoria = "Sottopeso"
        emoji = "🥗"
        suggerimento = "Aumenta l’apporto calorico."
    elif bmi < 25:
        categoria = "Peso ideale"
        emoji = "💪"
        suggerimento = "Continua con il tuo stile di vita!"
    elif bmi < 30:
        categoria = "Sovrappeso"
        emoji = "⚖️"
        suggerimento = "Riduci zuccheri e grassi."
    else:
        categoria = "Obesità"
        emoji = "🚨"
        suggerimento = "Serve un piano alimentare controllato."

    # Personalizzazioni
    if eta > 55 and bmi < 20:
        suggerimento += " Dopo i 55 anni un BMI leggermente più alto è comune."

    if sesso.lower().startswith("f") and bmi < 18.5:
        suggerimento += " Verifica l’apporto proteico."

    return {
        "bmi": bmi,
        "categoria": categoria,
        "emoji": emoji,
        "suggerimento": suggerimento
    }


# ===============================================
# ENDPOINT (SE USATO IN MODO STANDALONE)
# ===============================================
def endpoint_bmi():
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    peso = float(data.get("peso", 0))
    altezza = float(data.get("altezza", 0))
    eta = int(data.get("eta", 0))
    sesso = data.get("sesso", "N/D")

    risultato = calcola_bmi(peso, altezza, eta, sesso)
    return jsonify(risultato)
