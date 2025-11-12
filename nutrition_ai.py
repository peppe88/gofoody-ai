from datetime import datetime
import os
from flask import request, jsonify

# ===========================
# CONFIG SICUREZZA
# ===========================
AI_KEY = os.getenv("AI_KEY", "gofoody_3f8G7pLzR!x2N9tQ@uY5aWsE#jD6kHrV^m1ZbTqL4cP0oFi")  # stessa chiave usata nel PHP

def verifica_chiave():
    """Verifica che la richiesta contenga la chiave API corretta."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ")[1]
    return token == AI_KEY


# ===========================
# FUNZIONE PRINCIPALE BMI
# ===========================
def calcola_bmi(peso, altezza, eta, sesso):
    """
    Calcola il BMI e restituisce una valutazione con suggerimento nutrizionale.
    """

    # Validazione base
    if altezza <= 0 or peso <= 0:
        return {
            "bmi": None,
            "categoria": "Dati non validi",
            "suggerimento": "Inserisci peso e altezza per calcolare il tuo BMI."
        }

    altezza_m = altezza / 100  # conversione in metri
    bmi = round(peso / (altezza_m ** 2), 1)

    # Classificazione standard OMS
    if bmi < 18.5:
        categoria = "Sottopeso"
        emoji = "🥗"
        suggerimento = "Aumenta l’apporto calorico con pasti nutrienti e regolari."
    elif bmi < 25:
        categoria = "Peso ideale"
        emoji = "💪"
        suggerimento = "Mantieni il tuo stile di vita equilibrato e attivo!"
    elif bmi < 30:
        categoria = "Sovrappeso"
        emoji = "⚖️"
        suggerimento = "Riduci zuccheri e grassi, punta su pasti più leggeri."
    else:
        categoria = "Obesità"
        emoji = "🚨"
        suggerimento = "Consulta un nutrizionista per un piano alimentare bilanciato."

    # Personalizzazione in base all’età
    if eta and eta > 55 and bmi < 20:
        suggerimento += " Dopo i 55 anni, un BMI leggermente più alto può essere fisiologico."
    if sesso and sesso.lower().startswith("f") and bmi < 18.5:
        suggerimento += " Assicurati di avere un apporto proteico adeguato."

    risultato = {
        "bmi": bmi,
        "categoria": categoria,
        "emoji": emoji,
        "suggerimento": suggerimento
    }
    return risultato


# ===========================
# ENDPOINT (opzionale se usato standalone)
# ===========================
def endpoint_bmi():
    """Endpoint Flask che gestisce la chiamata /ai/nutrizione"""
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    peso = float(data.get("peso", 0))
    altezza = float(data.get("altezza", 0))
    eta = int(data.get("eta", 0))
    sesso = data.get("sesso", "N/D")

    risultato = calcola_bmi(peso, altezza, eta, sesso)
    return jsonify(risultato)
