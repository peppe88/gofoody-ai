from flask import Flask, request, jsonify
import pandas as pd
import os
from functools import wraps
from flask_cors import CORS
import json

# ===============================
# MODULI LOCALI (IMPORT PRINCIPALI)
# ===============================
try:
    from nutrition_ai import calcola_bmi
    from dispensa_ai import suggerisci_usi
    from coach import genera_messaggio
    from utils import match_ricette, genera_procedimento
    from chat import register_chat_routes  # ✅ Import chat AI
    print("✅ Moduli AI caricati correttamente.")
except ImportError as e:
    print("⚠️ Errore import moduli AI:", e)

    # fallback minimo (solo se Render non trova i moduli)
    def calcola_bmi(peso, altezza, eta, sesso):
        bmi = round(peso / ((altezza / 100) ** 2), 1) if altezza > 0 else 0
        categoria = (
            "Sottopeso" if bmi < 18.5 else
            "Normopeso" if bmi < 25 else
            "Sovrappeso" if bmi < 30 else
            "Obesità"
        )
        return {
            "bmi": bmi,
            "categoria": categoria,
            "suggerimento": "Mantieni uno stile di vita equilibrato."
        }

    def suggerisci_usi(dispensa):
        testo = []
        for item in dispensa:
            nome = item.get("nome", "Ingrediente").capitalize()
            scadenza = item.get("scadenza", "")
            testo.append(f"📦 Usa presto {nome}" + (f" (scade il {scadenza})" if scadenza else ""))
        return testo

    def genera_messaggio(bmi, dieta, trend):
        return f"Il tuo BMI è {bmi}. Continua con la dieta {dieta or 'bilanciata'}!"

    def match_ricette(recipes, dispensa, allergie, preferenze):
        return [
            {"titolo": "Pasta al pomodoro", "ingredienti": ["pasta", "pomodoro", "olio"], "tempo": "15 min", "descrizione": "Classico primo piatto italiano."},
            {"titolo": "Insalata mista", "ingredienti": ["lattuga", "pomodoro", "olio"], "tempo": "10 min", "descrizione": "Fresca e leggera."}
        ]

    def genera_procedimento(titolo, ingredienti, dieta):
        if not ingredienti:
            return "⚠️ Nessun ingrediente specificato per questa ricetta."
        intro = f"🍽️ Oggi prepariamo *{titolo.lower()}*, un piatto {dieta.lower() if dieta else 'semplice'} e gustoso."
        corpo = [
            f"1️⃣ Prepara con cura {', '.join(ingredienti[:3])}.",
            "2️⃣ Scalda una padella con un filo d’olio e aggiungi gli ingredienti principali.",
            "3️⃣ Cuoci lentamente finché non ottieni una consistenza perfetta.",
            f"4️⃣ Servi e gusta la tua {titolo.lower()} — sana e deliziosa!"
        ]
        return "\n".join([intro] + corpo)

    register_chat_routes = None  # evita NameError se non importata


# ===============================
# CARICAMENTO RICETTE E NUTRIENTI
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Carica ricette italiane
try:
    with open(os.path.join(BASE_DIR, "data", "italian_recipes.json"), "r", encoding="utf-8") as f:
        ITALIAN_RECIPES = json.load(f)
    print("✅ italian_recipes.json caricato")
except Exception as e:
    print("❌ Errore caricamento italian_recipes.json:", e)
    ITALIAN_RECIPES = {}

# Carica database nutrizionale FoodData Central
try:
    with open(os.path.join(BASE_DIR, "data", "FoodData_Central.json"), "r", encoding="utf-8") as f:
        NUTRIENT_DB = json.load(f)
    print("✅ FoodData_Central.json caricato")
except Exception as e:
    print("❌ Errore caricamento FoodData_Central.json:", e)
    NUTRIENT_DB = {}


# ===============================
# FUNZIONI UTILI MEAL AI ENGINE
# ===============================
def normalizza_unita(q):
    """Converte kg/g/mg/L/ml in grammi. ml≈g per semplicità."""
    if not isinstance(q, str):
        return 0
    s = q.lower().strip()
    import re
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", s)
    if not m:
        return 0

    num = float(m.group(1))

    if "kg" in s:
        return num * 1000
    if s.endswith("g") or " g" in s:
        return num
    if "mg" in s:
        return num / 1000
    if "l" in s and "ml" not in s:
        return num * 1000
    if "ml" in s:
        return num

    return num


def stima_fattore_scala(q_input, ricetta):
    """Scala la ricetta rispetto al peso totale del piatto."""
    base_peso = ricetta.get("peso_totale_piatto_g", 300)
    q_norm = normalizza_unita(q_input)
    if q_norm <= 0:
        return 1
    return q_norm / base_peso


def get_kcal_ingrediente(nome, quantita_g):
    """Calcola le kcal partendo da FoodData_Central.json"""
    nome = nome.lower().strip()
    for item in NUTRIENT_DB:
        if item.get("nome", "").lower() == nome:
            kcal100 = item.get("kcal_100g", 0)
            return (quantita_g * kcal100) / 100
    return 0


# ===============================
# CONFIGURAZIONE BASE FLASK
# ===============================
app = Flask(__name__)
CORS(app, resources={r"/ai/*": {"origins": "*"}}, supports_credentials=False)

# Registra le rotte Chat AI solo se disponibili
if register_chat_routes:
    register_chat_routes(app)
else:
    print("⚠️ Chat AI non attiva: register_chat_routes non trovato")


# Chiave segreta per chiamate da PHP
API_KEY = os.getenv(
    "AI_KEY",
    "gofoody_3f8G7pLzR!x2N9tQ@uY5aWsE#jD6kHrV^m1ZbTqL4cP0oFi"
)


# ===============================
# DECORATORE AUTENTICAZIONE
# ===============================
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "API key missing"}), 401
        token = auth.replace("Bearer ", "").strip()
        if token != API_KEY:
            return jsonify({"error": "Invalid API key"}), 403
        return f(*args, **kwargs)
    return decorated


# ===============================
# ENDPOINT HEALTH CHECK
# ===============================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "AI online ✅",
        "message": "Flask funziona correttamente.",
        "routes": [
            "/ai/meal", "/ai/nutrizione", "/ai/ricetta",
            "/ai/procedimento", "/ai/coach", "/ai/dispensa", "/ai/chat"
        ]
    })


# ===============================
# ENDPOINT RICETTE
# ===============================
@app.route("/ai/ricetta", methods=["POST"])
@require_api_key
def ai_ricetta():
    data = request.get_json(force=True)
    dispensa = set(i.lower() for i in data.get("dispensa", []))
    dieta = data.get("dieta", "")
    allergie = set(i.lower() for i in data.get("allergie", []))
    preferenze = set(i.lower() for i in data.get("preferenze", []))

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
@require_api_key
def ai_procedimento():
    data = request.get_json(force=True)
    titolo = data.get("titolo", "Ricetta")
    ingredienti = data.get("ingredienti", [])
    dieta = data.get("dieta", "")
    testo = genera_procedimento(titolo, ingredienti, dieta)
    return jsonify({"procedimento": testo})


# ===============================
# ENDPOINT MEAL (NUOVO)
# ===============================
@app.route("/ai/meal", methods=["POST"])
@require_api_key
def ai_meal():
    data = request.get_json(force=True)
    alimento = data.get("alimento", "").lower().strip()
    quantita = data.get("quantita", "0")
    porzioni = float(data.get("porzioni", 1))

    # 1) Trova ricetta
    ricetta = None
    key_match = alimento.replace(" ", "_")
    if key_match in ITALIAN_RECIPES:
        ricetta = ITALIAN_RECIPES[key_match]
    else:
        for k in ITALIAN_RECIPES:
            if alimento in k.replace("_", " "):
                ricetta = ITALIAN_RECIPES[k]
                break

    if not ricetta:
        return jsonify({"error": "RICETTA_NON_TROVATA"}), 404

    # 2) Fattore scala
    fattore = stima_fattore_scala(quantita, ricetta)

    ingredienti_finali = []
    kcal_tot = 0

    for ing in ricetta.get("ingredienti", []):
        nome = ing["nome"]
        base_q = float(ing["quantita_g"])
        q_finale = base_q * fattore * porzioni

        kcal_ing = get_kcal_ingrediente(nome, q_finale)
        kcal_tot += kcal_ing

        ingredienti_finali.append({
            "nome": nome,
            "quantita_g": round(q_finale, 1),
            "kcal": round(kcal_ing, 1)
        })

    return jsonify({
        "titolo": ricetta.get("titolo", alimento),
        "alimento_originale": alimento,
        "porzioni": porzioni,
        "fattore_scala": round(fattore, 3),
        "ingredienti": ingredienti_finali,
        "kcal_totali": round(kcal_tot, 1)
    })


# ===============================
# ENDPOINT NUTRIZIONE
# ===============================
@app.route("/ai/nutrizione", methods=["POST"])
@require_api_key
def ai_nutrizione():
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
@require_api_key
def ai_dispensa():
    data = request.get_json(force=True)
    dispensa = data.get("dispensa", [])
    risultati = suggerisci_usi(dispensa)
    return jsonify({"alert": risultati})


# ===============================
# ENDPOINT COACH
# ===============================
@app.route("/ai/coach", methods=["POST"])
@require_api_key
def ai_coach():
    data = request.get_json(force=True)
    bmi = data.get("bmi", 0)
    dieta = data.get("dieta", "")
    trend = data.get("trend_peso", "stabile")

    messaggio = genera_messaggio(bmi, dieta, trend)
    return jsonify({"coach_message": messaggio})


# ===============================
# ENDPOINT CHAT AI
# ===============================
@app.route("/ai/chat", methods=["POST"])
def ai_chat_direct():
    try:
        from chat import recupera_memoria, genera_risposta_locale, salva_conversazione
    except Exception as e:
        print("❌ Errore import chat.py:", e)
        return jsonify({"risposta": "Errore interno AI."}), 500

    try:
        data = request.get_json(force=True, silent=True) or {}
        prompt = data.get("prompt", "").strip()
        id_utente = int(data.get("id_utente", 0))
        if not prompt:
            return jsonify({"risposta": "Scrivimi qualcosa 😊"})
    except Exception as e:
        print("⚠️ Errore parsing:", e)
        return jsonify({"risposta": "Richiesta non valida."}), 400

    try:
        memoria = recupera_memoria(id_utente)
        risposta = genera_risposta_locale(prompt, memoria)
        salva_conversazione(id_utente, prompt, risposta)
        print(f"💬 [AI] Utente {id_utente}: {prompt} → {risposta}")
        return jsonify({"risposta": risposta})
    except Exception as e:
        print("⚠️ Errore AI interno:", e)
        return jsonify({"risposta": "AI non disponibile."}), 500


# ===============================
# AVVIO SERVER LOCALE
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
