# ================================================================
#  GoFoody AI - chat.py
#  Gestione chat intelligente locale con apprendimento su MySQL
# ================================================================

import mysql.connector
from datetime import datetime
import random

# ------------------------------------------------
# CONFIGURAZIONE DATABASE AI
# ------------------------------------------------
DB_CONFIG = {
    "host": "31.11.39.251",
    "user": "Sql1897455",
    "password": "Peppino_88",
    "database": "Sql1897455_3"
}


# ================================================================
# FUNZIONI DI SUPPORTO
# ================================================================

def salva_conversazione(id_utente, prompt, risposta):
    """Salva una riga di conversazione nel DB AI"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversazioni_ai (id_utente, prompt, risposta) VALUES (%s, %s, %s)",
            (id_utente, prompt, risposta)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ Errore salvataggio conversazione:", e)


def recupera_memoria(id_utente, limit=10):
    """Recupera le ultime interazioni dell’utente dal DB"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT prompt, risposta FROM conversazioni_ai WHERE id_utente=%s ORDER BY id DESC LIMIT %s",
            (id_utente, limit)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows[::-1]  # Restituisce in ordine cronologico
    except Exception as e:
        print("⚠️ Errore recupero memoria:", e)
        return []


# ================================================================
# GENERATORE DI RISPOSTE
# ================================================================

def genera_risposta_locale(prompt, memoria):
    """
    Genera una risposta pseudo-intelligente basata sul prompt e
    sulla memoria recente dell’utente.
    """
    p = prompt.lower()

    # Risposte contestuali “fisse” (domini GoFoody)
    if "ciao" in p or "salve" in p:
        return "Ciao 👋! Sono GoFoody AI, il tuo assistente in cucina. Cosa vuoi cucinare oggi?"
    if "ricetta" in p:
        return "Certo! Dimmi cosa hai in dispensa e ti suggerisco un piatto adatto 🍝"
    if "dispensa" in p:
        return "Apri la tua dispensa digitale: posso dirti cosa consumare prima per evitare sprechi 🧺"
    if "dieta" in p or "alimentazione" in p:
        return "Vuoi un consiglio per la tua dieta? Posso adattare i suggerimenti alla dieta Mediterranea, Vegana o Vegetariana 🥦"
    if "consiglio" in p or "help" in p or "aiuto" in p:
        return "Eccomi 👨‍🍳! Posso aiutarti a creare un piano alimentare, trovare ricette o gestire la tua dispensa!"

    # Se l’argomento è già apparso in memoria
    for chat in reversed(memoria):
        if prompt.lower() in chat["prompt"].lower():
            return f"Ne avevamo già parlato! Ti avevo detto: {chat['risposta']}"

    # Risposte generiche casuali (fallback)
    return random.choice([
        "Interessante! Raccontami meglio cosa vuoi preparare 🍽️",
        "Mh, non ho capito bene... vuoi un consiglio su una ricetta o sulla dieta?",
        "Posso cercare tra le tue ricette preferite per aiutarti 💡",
        "Parlami di cosa hai in dispensa e troveremo insieme qualcosa di buono 😋"
    ])


# ================================================================
# ENDPOINT FLASK
# ================================================================

def register_chat_routes(app):
    """Registra l’endpoint /ai/chat nell’app Flask"""

    @app.route("/ai/chat", methods=["POST"])
    def ai_chat():
        """
        Gestisce la chat AI locale.
        Richiede JSON: {"prompt": "testo", "id_utente": 1}
        Restituisce: {"risposta": "..."}
        """
        data = app.current_request.get_json(force=True) if hasattr(app, 'current_request') else None
        if not data:
            from flask import request
            data = request.get_json(force=True)

        prompt = data.get("prompt", "").strip()
        id_utente = int(data.get("id_utente", 0))

        if not prompt:
            return {"risposta": "Scrivimi qualcosa e ti risponderò 😊"}

        memoria = recupera_memoria(id_utente)
        risposta = genera_risposta_locale(prompt, memoria)

        salva_conversazione(id_utente, prompt, risposta)

        return {"risposta": risposta}
