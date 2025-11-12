from datetime import datetime, timedelta
import os
from flask import request, jsonify

# ===========================
# CONFIG SICUREZZA
# ===========================
AI_KEY = os.getenv("AI_KEY", "gofoody_3f8G7pLzR!x2N9tQ@uY5aWsE#jD6kHrV^m1ZbTqL4cP0oFi")  # stessa chiave del PHP

def verifica_chiave():
    """Verifica che la richiesta contenga la chiave API corretta."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ")[1]
    return token == AI_KEY


# ===========================
# FUNZIONE PRINCIPALE
# ===========================
def suggerisci_usi(dispensa):
    """
    Analizza una lista di alimenti e restituisce suggerimenti su cosa consumare prima.
    
    Parametri:
        dispensa: elenco di dizionari, es.
        [
            {"nome": "Pomodori", "scadenza": "2025-11-13"},
            {"nome": "Latte", "scadenza": "2025-11-12"},
            {"nome": "Pasta", "scadenza": ""}
        ]
    """
    oggi = datetime.now().date()
    suggerimenti = []
    
    for item in dispensa:
        nome = item.get("nome", "").capitalize().strip()
        scad_str = item.get("scadenza", "").strip()
        if not scad_str:
            continue
        
        try:
            data_scad = datetime.strptime(scad_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        giorni = (data_scad - oggi).days
        
        # Analisi temporale
        if giorni < 0:
            suggerimenti.append(f"⚠️ {nome} è scaduto da {-giorni} giorni!")
        elif giorni == 0:
            suggerimenti.append(f"⚠️ {nome} scade OGGI — consumalo subito!")
        elif giorni <= 2:
            suggerimenti.append(f"⏳ {nome} scade tra {giorni} giorni — usalo prima possibile.")
        elif giorni <= 5:
            suggerimenti.append(f"📅 {nome} è da consumare entro {giorni} giorni.")
        else:
            # Nessun alert per alimenti con scadenza lontana
            continue

    if not suggerimenti:
        suggerimenti.append("✅ Tutti gli alimenti in dispensa sono in buono stato.")

    return suggerimenti


# ===========================
# ENDPOINT (opzionale Flask)
# ===========================
def endpoint_dispensa():
    """Gestisce la chiamata /ai/dispensa"""
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    dispensa = data.get("dispensa", [])
    risultati = suggerisci_usi(dispensa)
    return jsonify({"alert": risultati})
