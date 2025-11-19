# ================================================================
#  GoFoody AI - chat.py (stabile, intelligente, fallback automatico)
# ================================================================

from flask import request, jsonify
import random
import difflib

# ---------------------------------------------------
# TENTATIVO IMPORT + TEST CONNESSIONE MYSQL
# ---------------------------------------------------

MYSQL_AVAILABLE = False
mysql = None

try:
    import mysql.connector
    mysql = mysql.connector
    # tentativo di connessione reale a Aruba
    try:
        test_conn = mysql.connect(
            host="31.11.39.251",
            user="Sql1897455",
            password="Peppino_88",
            database="Sql1897455_2",
            port=3306,
            connection_timeout=2
        )
        test_conn.close()
        MYSQL_AVAILABLE = True
        print("✅ MySQL Aruba raggiungibile: modalità avanzata attiva")
    except:
        print("⚠️ MySQL non raggiungibile: attivo fallback locale")
        MYSQL_AVAILABLE = False

except ImportError:
    print("⚠️ mysql.connector non disponibile: fallback attivo")
    MYSQL_AVAILABLE = False


# ---------------------------------------------------
# CONFIG DATABASE
# ---------------------------------------------------

DB_CONFIG = {
    "host": "31.11.39.251",
    "user": "Sql1897455",
    "password": "Peppino_88",
    "database": "Sql1897455_2",
    "port": 3306
}

def get_db():
    if not MYSQL_AVAILABLE:
        return None
    try:
        return mysql.connect(**DB_CONFIG)
    except:
        return None


# ---------------------------------------------------
# FALLBACK (come nel tuo file funzionante)
# ---------------------------------------------------

def fallback_response(prompt):
    p = prompt.lower()

    if "ciao" in p or "salve" in p:
        return "Ciao 👋! Sono GoFoody AI. Come posso aiutarti oggi?"

    if "ricetta" in p:
        return "Dimmi cosa hai in dispensa e ti suggerisco una ricetta 🍝"

    if "dispensa" in p:
        return "Posso dirti cosa consumare prima per evitare sprechi 📦"

    if "dieta" in p:
        return "Vuoi un consiglio per la tua dieta? 🥗"

    fallback = [
        "Interessante, dimmi di più 😄",
        "Vuoi un aiuto su calorie, dispensa o ricette giornaliere?",
        "Sono qui per aiutarti nella cucina di tutti i giorni 👨‍🍳"
    ]
    return random.choice(fallback)


# ---------------------------------------------------
# RISPOSTE AVANZATE BASATE SU INTENTI FROM DB
# ---------------------------------------------------

def load_intents():
    conn = get_db()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM ai_intenti WHERE attivo=1")
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def match_intent(prompt, intents):
    p = prompt.lower()
    best = None
    best_score = 0

    for intent in intents:
        for example in (intent["esempi_domande"] or "").split("\n"):
            s = difflib.SequenceMatcher(None, p, example.lower()).ratio()
            if s > best_score:
                best_score = s
                best = intent

    if best_score < 0.45:
        return None

    return best


def answer_from_intent(intent):
    if not intent["esempi_risposte"]:
        return intent["descrizione"] or "Posso aiutarti 😊"
    risposte = intent["esempi_risposte"].split("\n")
    return random.choice(risposte)


# ---------------------------------------------------
# ROUTE PRINCIPALE CHAT
# ---------------------------------------------------

def register_chat_routes(app):

    @app.route("/ai/chat", methods=["POST"])
    def chat_ai():
        data = request.get_json(force=True, silent=True) or {}
        prompt = (data.get("prompt") or "").strip()

        if not prompt:
            return jsonify({"risposta": "Scrivimi qualcosa 😊"})

        # modalità avanzata
        if MYSQL_AVAILABLE:
            intents = load_intents()
            if intents:
                match = match_intent(prompt, intents)
                if match:
                    risposta = answer_from_intent(match)
                    return jsonify({"risposta": risposta})

        # fallback sicuro (identico al tuo file funzionante)
        return jsonify({"risposta": fallback_response(prompt)})
