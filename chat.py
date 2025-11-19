# ================================================================
#  GoFoody AI - chat.py (Versione B: avanzata + MySQL Aruba)
#  - Usa ai_intenti per capire la domanda
#  - Usa ai_fatti_utente per personalizzare le risposte
#  - NON genera ricette, ma guida e consiglia sull’app
#  - Ha un fallback locale se MySQL non è disponibile
# ================================================================

from flask import request, jsonify
import random
import difflib

# ================================================================
# TENTATIVO IMPORT MySQL (compatibile con Render)
# ================================================================
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    mysql = None
    MYSQL_AVAILABLE = False
    print("⚠️ Modulo mysql.connector non disponibile: la chat userà il fallback senza DB.")

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
    """Ritorna una connessione MySQL o None se non disponibile."""
    if not MYSQL_AVAILABLE:
        return None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
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

    # Supporta separazione con newline, punto e virgola o doppio pipe
    raw = text.replace("\r", "\n")
    parts = []
    for chunk in raw.split("\n"):
        if "||" in chunk:
            parts.extend(chunk.split("||"))
        elif ";" in chunk:
            parts.extend(chunk.split(";"))
        else:
            parts.append(chunk)

    cleaned = [p.strip(" -•\t ") for p in parts if p.strip()]
    return cleaned


def load_intents():
    """Carica gli intenti attivi da ai_intenti."""
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
            "id": r.get("id"),
            "nome": r.get("nome") or "",
            "descrizione": r.get("descrizione") or "",
            "categoria": r.get("categoria") or "",
            "domande": parse_examples(r.get("esempi_domande")),
            "risposte": parse_examples(r.get("esempi_risposte")),
        })
    return intents


def load_user_facts(id_utente, limit=20):
    """Carica i fatti utente da ai_fatti_utente (ordinati per importanza e recenza)."""
    if not id_utente:
        return []

    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT tipo, valore, importance
            FROM ai_fatti_utente
            WHERE id_utente = %s
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
            """,
            (int(id_utente), int(limit))
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print("⚠️ Errore lettura ai_fatti_utente:", e)
        return []


def match_intent(prompt, intents):
    """Trova l’intento migliore rispetto al prompt usando fuzzy matching."""
    if not intents:
        return None, 0.0

    p = (prompt or "").lower().strip()
    if not p:
        return None, 0.0

    best_intent = None
    best_score = 0.0

    for intent in intents:
        # Bonus se il nome dell’intento è contenuto nel messaggio
        nome = (intent["nome"] or "").lower()
        if nome and nome in p:
            score = 0.95
        else:
            score = 0.0

        for domanda in intent["domande"]:
            d = domanda.lower()
            # se la domanda è quasi contenuta nel messaggio
            if d in p or p in d:
                local_score = 0.9
            else:
                local_score = difflib.SequenceMatcher(None, p, d).ratio()

            if local_score > score:
                score = local_score

        if score > best_score:
            best_score = score
            best_intent = intent

    # Soglia minima: se è troppo basso, meglio il fallback
    if best_score < 0.45:
        return None, best_score

    return best_intent, best_score


def build_personalization_snippet(facts):
    """Costruisce una piccola frase umanizzata con i fatti utente (se presenti)."""
    if not facts:
        return ""

    dieta = None
    obiettivo = None
    allergie = None

    for f in facts:
        tipo = (f.get("tipo") or "").lower()
        val = (f.get("valore") or "").strip()

        if not val:
            continue

        if "dieta" in tipo and not dieta:
            dieta = val
        elif ("obiettivo" in tipo or "goal" in tipo) and not obiettivo:
            obiettivo = val
        elif ("allerg" in tipo or "intoller" in tipo) and not allergie:
            allergie = val

    parts = []
    if dieta:
        parts.append(f"so che stai seguendo una dieta <strong>{dieta}</strong>")
    if obiettivo:
        parts.append(f"e che il tuo obiettivo è <strong>{obiettivo}</strong>")
    if allergie:
        parts.append(f"e che devi fare attenzione a <strong>{allergie}</strong>")

    if not parts:
        return ""

    frase = "Piccolo promemoria su di te: " + ", ".join(parts) + "."
    return frase


def generate_answer_from_intent(intent, facts, prompt):
    """Genera una risposta umanizzata a partire da un intento + fatti utente."""
    base_responses = intent.get("risposte") or []
    if base_responses:
        # Prendiamo una risposta di base a caso
        risposta = random.choice(base_responses).strip()
    else:
        # Se non ci sono risposte predefinite
        nome = intent.get("nome") or "questa sezione"
        risposta = f"Ti posso aiutare per tutto ciò che riguarda {nome} in GoFoody. Dimmi pure cosa ti serve in dettaglio 😊"

    # Personalizzazione con fatti utente
    personalizzazione = build_personalization_snippet(facts)
    if personalizzazione:
        risposta = f"{risposta}\n\n{personalizzazione}"

    # Un piccolo tocco finale più caldo
    risposta += "\n\nSe vuoi, posso anche guidarti passo passo nell’app 😉"
    return risposta


# ================================================================
# FALLBACK: CHAT LOCALE SENZA DB
# ================================================================
def fallback_chat_response(prompt):
    """Risposta di emergenza se DB non è disponibile o nessun intento trovato."""
    p = (prompt or "").lower()

    if "ciao" in p or "salve" in p or "buongiorno" in p:
        return "Ciao 👋! Sono GoFoody AI. Posso aiutarti a usare l’app: dispensa, calorie, ricette giornaliere e tanto altro."

    if "dispensa" in p:
        return (
            "La sezione <strong>Dispensa</strong> ti permette di tenere traccia di quello che hai in casa "
            "e di vedere cosa consumare prima per evitare sprechi. Puoi aggiungere, modificare o eliminare prodotti."
        )

    if "calorie" in p or "kcal" in p:
        return (
            "GoFoody calcola le <strong>calorie giornaliere</strong> in base ai pasti che registri con il tasto "
            "“Ho mangiato qualcosa” o dalla sezione ricette. Così vedi subito quanto hai mangiato oggi."
        )

    if "ricette" in p:
        return (
            "Nella sezione <strong>Ricette giornaliere</strong> trovi idee basate su ciò che hai in dispensa e sulle tue preferenze. "
            "Io non cucino al posto tuo 😄 ma ti aiuto a capire dove trovare cosa."
        )

    if "bmi" in p or "peso" in p or "dieta" in p:
        return (
            "Dalla sezione <strong>Profilo</strong> puoi inserire peso, altezza e stile alimentare. "
            "Così GoFoody può darti suggerimenti più mirati e calcolare indicatori come il BMI."
        )

    generic = [
        "Posso aiutarti a capire come usare GoFoody giorno per giorno: dimmi cosa vuoi fare e ti guido io 👨‍🍳",
        "Vuoi un aiuto su dispensa, calorie, ricette giornaliere o profilo? Dimmi pure cosa ti interessa di più 😊",
        "GoFoody ti aiuta a mangiare meglio, sprecare meno e tenere tutto sotto controllo. Dimmi da dove vuoi iniziare 💚",
    ]
    return random.choice(generic)


# ================================================================
# REGISTRAZIONE ROTTE CHAT
# ================================================================
def register_chat_routes(app):
    """Registra l’endpoint /ai/chat nell’app Flask principale."""

    @app.route("/ai/chat", methods=["POST"])
    def ai_chat():
        try:
            data = request.get_json(force=True, silent=True) or {}
            prompt = (data.get("prompt") or "").strip()
            id_utente = int(data.get("id_utente") or 0)
        except Exception as e:
            print("❌ Errore parsing JSON chat:", e)
            return jsonify({"risposta": "C'è stato un problema nel leggere il tuo messaggio 😅"}), 400

        if not prompt:
            return jsonify({"risposta": "Scrivimi qualcosa e ti aiuto volentieri 😊"})

        # 1) Se DB disponibile → usiamo intenti + fatti utente
        if MYSQL_AVAILABLE:
            intents = load_intents()
            facts = load_user_facts(id_utente)
            intent, score = match_intent(prompt, intents)

            print(f"🔍 Chat AI - utente {id_utente}, intento_match={intent['nome'] if intent else 'None'}, score={score:.2f}")

            if intent:
                risposta = generate_answer_from_intent(intent, facts, prompt)
            else:
                # Nessun intento chiaro → fallback guidato ma comunque amichevole
                risposta = fallback_chat_response(prompt)
        else:
            # 2) Nessun DB → fallback totale
            risposta = fallback_chat_response(prompt)

        return jsonify({"risposta": risposta})
