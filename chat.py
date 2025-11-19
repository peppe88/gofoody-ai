# ================================================================
#  GoFoody AI - chat.py (Versione B: avanzata + MySQL Aruba)
#  - Usa ai_intenti per capire la domanda
#  - Usa ai_fatti_utente per personalizzare la risposta
#  - Non inventa ricette, guida l’utente nell'app
#  - Se MySQL non è disponibile → fallback elegante
# ================================================================

from flask import request, jsonify
import random
import difflib

# ================================================================
# IMPORT MYSQL (Render può non averlo)
# ================================================================
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    print("⚠️ mysql.connector NON disponibile → la chat userà il fallback.")

# ================================================================
# CONFIG DB ARUBA
# ================================================================
DB_CONFIG = {
    "host": "31.11.39.251",
    "user": "Sql1897455",
    "password": "Peppino_88",
    "database": "Sql1897455_2",
    "port": 3306,
}

def get_db_connection():
    """Crea connessione MySQL se disponibile."""
    if not MYSQL_AVAILABLE:
        return None
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        print("❌ Errore connessione MySQL:", e)
        return None


# ================================================================
# UTIL PER INTENTI E FATTI UTENTE
# ================================================================
def parse_examples(text):
    """Converte esempi_domande/esempi_risposte in lista pulita."""
    if not text:
        return []
    raw = text.replace("\r", "\n")
    parts = []
    for line in raw.split("\n"):
        if "||" in line:
            parts.extend(line.split("||"))
        elif ";" in line:
            parts.extend(line.split(";"))
        else:
            parts.append(line)
    return [p.strip(" -•\t ") for p in parts if p.strip()]


def load_intents():
    """Carica gli intenti attivi dal DB."""
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM ai_intenti WHERE attivo = 1")
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print("⚠️ Errore lettura ai_intenti:", e)
        return []

    intents = []
    for r in rows:
        intents.append({
            "id": r["id"],
            "nome": r["nome"],
            "descrizione": r.get("descrizione", ""),
            "categoria": r.get("categoria", ""),
            "domande": parse_examples(r.get("esempi_domande")),
            "risposte": parse_examples(r.get("esempi_risposte")),
        })
    return intents


def load_user_facts(id_utente, limit=20):
    """Carica i fatti utente ordinati per importanza e recenza."""
    if not id_utente:
        return []

    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT tipo, valore, importance
            FROM ai_fatti_utente
            WHERE id_utente = %s
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
        """, (id_utente, limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print("⚠️ Errore lettura ai_fatti_utente:", e)
        return []


def match_intent(prompt, intents):
    """Trova l’intento più simile al messaggio dell'utente."""
    p = prompt.lower()
    best_score = 0
    best_intent = None

    for intent in intents:
        score = 0

        # bonus se il nome dell’intento è contenuto nel messaggio
        if intent["nome"].lower() in p:
            score = 0.95

        for esempio in intent["domande"]:
            e = esempio.lower()
            if e in p or p in e:
                local = 0.9
            else:
                local = difflib.SequenceMatcher(None, p, e).ratio()
            if local > score:
                score = local

        if score > best_score:
            best_score = score
            best_intent = intent

    if best_score < 0.45:
        return None, best_score

    return best_intent, best_score


def build_personalization_snippet(facts):
    """Usa i fatti utente per creare una frase personalizzata."""
    if not facts:
        return ""

    dieta = None
    obiettivo = None
    allergie = None

    for f in facts:
        tipo = f["tipo"].lower()
        val = f["valore"]

        if "dieta" in tipo and not dieta:
            dieta = val
        elif ("obiettivo" in tipo or "goal" in tipo) and not obiettivo:
            obiettivo = val
        elif ("allerg" in tipo or "intoller" in tipo) and not allergie:
            allergie = val

    parts = []
    if dieta: parts.append(f"dieta <strong>{dieta}</strong>")
    if obiettivo: parts.append(f"obiettivo <strong>{obiettivo}</strong>")
    if allergie: parts.append(f"allergie <strong>{allergie}</strong>")

    if not parts:
        return ""

    return "Piccolo promemoria su di te: " + ", ".join(parts) + "."


def generate_answer_from_intent(intent, facts):
    """Costruisce la risposta finale completa."""
    base_list = intent["risposte"]
    if base_list:
        risposta = random.choice(base_list)
    else:
        risposta = f"Posso aiutarti nella sezione {intent['nome']} di GoFoody 😊"

    pers = build_personalization_snippet(facts)
    if pers:
        risposta += "<br><br>" + pers

    risposta += "<br><br>Se vuoi ti guido passo passo 😉"
    return risposta


# ================================================================
# FALLBACK SE DB NON DISPONIBILE
# ================================================================
def fallback_chat_response(prompt):
    p = prompt.lower()

    if "ciao" in p:
        return "Ciao 👋! Sono GoFoody AI. Posso aiutarti a usare l’app!"

    generic = [
        "Dimmi pure cosa desideri fare in GoFoody e ti guido io 😊",
        "Vuoi gestire la dispensa, controllare le calorie o trovare ricette giornaliere?",
        "Sono qui per aiutarti a usare GoFoody al meglio 💚"
    ]
    return random.choice(generic)


# ================================================================
# REGISTRAZIONE ENDPOINT CHAT
# ================================================================
def register_chat_routes(app):

    @app.route("/ai/chat", methods=["POST"])
    def ai_chat():
        data = request.get_json(force=True, silent=True) or {}
        prompt = (data.get("prompt") or "").strip()
        id_utente = int(data.get("id_utente") or 0)

        if not prompt:
            return jsonify({"risposta": "Scrivimi un messaggio 😊"})

        # Se DB disponibile → AI completa
        if MYSQL_AVAILABLE:
            intents = load_intents()
            facts = load_user_facts(id_utente)
            intent, score = match_intent(prompt, intents)

            print(f"🔍 MATCH → utente={id_utente}, intento={intent['nome'] if intent else 'None'}, score={score}")

            if intent:
                risposta = generate_answer_from_intent(intent, facts)
            else:
                risposta = fallback_chat_response(prompt)

        else:
            # No MySQL → fallback
            risposta = fallback_chat_response(prompt)

        return jsonify({"risposta": risposta})
