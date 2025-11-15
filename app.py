from flask import Flask, request, jsonify
import pandas as pd
import os
from functools import wraps
from flask_cors import CORS
import json
import difflib

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
            testo.append(
                f"📦 Usa presto {nome}"
                + (f" (scade il {scadenza})" if scadenza else "")
            )
        return testo

    def genera_messaggio(bmi, dieta, trend):
        return f"Il tuo BMI è {bmi}. Continua con la dieta {dieta or 'bilanciata'}!"

    def match_ricette(recipes, dispensa, allergie, preferenze):
        return [
            {
                "titolo": "Pasta al pomodoro",
                "ingredienti": ["pasta", "pomodoro", "olio"],
                "tempo": "15 min",
                "descrizione": "Classico primo piatto italiano."
            },
            {
                "titolo": "Insalata mista",
                "ingredienti": ["lattuga", "pomodoro", "olio"],
                "tempo": "10 min",
                "descrizione": "Fresca e leggera."
            }
        ]

    def genera_procedimento(titolo, ingredienti, dieta):
        if not ingredienti:
            return "⚠️ Nessun ingrediente specificato per questa ricetta."
        intro = (
            f"🍽️ Oggi prepariamo *{titolo.lower()}*, "
            f"un piatto {dieta.lower() if dieta else 'semplice'} e gustoso."
        )
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

# Carica ricette italiane (base)
try:
    with open(
        os.path.join(BASE_DIR, "data", "italian_recipes.json"),
        "r",
        encoding="utf-8"
    ) as f:
        ITALIAN_RECIPES = json.load(f)
    if not isinstance(ITALIAN_RECIPES, dict):
        ITALIAN_RECIPES = {}
    print("✅ italian_recipes.json caricato")
except Exception as e:
    print("❌ Errore caricamento italian_recipes.json:", e)
    ITALIAN_RECIPES = {}

# Carica ricette utente (personalizzate)
USER_RECIPES_PATH = os.path.join(BASE_DIR, "data", "user_recipes.json")
try:
    if os.path.exists(USER_RECIPES_PATH):
        with open(USER_RECIPES_PATH, "r", encoding="utf-8") as f:
            USER_RECIPES = json.load(f)
        if not isinstance(USER_RECIPES, dict):
            USER_RECIPES = {}
    else:
        USER_RECIPES = {}
    print("✅ user_recipes.json caricato (o inizializzato)")
except Exception as e:
    print("❌ Errore caricamento user_recipes.json:", e)
    USER_RECIPES = {}

# Carica database nutrizionale FoodData Central
try:
    with open(
        os.path.join(BASE_DIR, "data", "FoodData_Central.json"),
        "r",
        encoding="utf-8"
    ) as f:
        NUTRIENT_DB = json.load(f)
    if not isinstance(NUTRIENT_DB, list):
        NUTRIENT_DB = []
    print("✅ FoodData_Central.json caricato")
except Exception as e:
    print("❌ Errore caricamento FoodData_Central.json:", e)
    NUTRIENT_DB = []


def save_user_recipes():
    """Salva il dizionario USER_RECIPES su file JSON."""
    try:
        os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
        with open(USER_RECIPES_PATH, "w", encoding="utf-8") as f:
            json.dump(USER_RECIPES, f, ensure_ascii=False, indent=2)
        print("💾 user_recipes.json aggiornato")
    except Exception as e:
        print("❌ Errore salvataggio user_recipes.json:", e)


# ===============================
# FUNZIONI UTILI MEAL AI ENGINE
# ===============================
def normalizza_nome_alimento_py(nome: str) -> str:
    """
    Normalizza il nome di un alimento/ingrediente/piatto:
    - minuscole
    - rimozione punteggiatura
    - stopwords
    - sinonimi estesi (pomodorini/ciliegini/datterini, formati pasta, ecc.)
    """
    if not isinstance(nome, str):
        return ""

    s = nome.strip().lower()

    import re
    # rimuovo punteggiatura base
    s = re.sub(r"[^a-zàèéìòù0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # normalizzazione frasi/sinonimi multi-parola
    phrase_map = {
        "olio evo": "olio extravergine di oliva",
        "olio extra vergine": "olio extravergine di oliva",
        "olio extravergine": "olio extravergine di oliva",
        "olio di oliva": "olio extravergine di oliva",
        "olio d oliva": "olio extravergine di oliva",
        "passata di pomodoro": "passata di pomodoro",
        "passata pomodoro": "passata di pomodoro",
        "salsa di pomodoro": "passata di pomodoro",
        "parmigiano reggiano": "parmigiano",
        "grana padano": "parmigiano",
        "petto di pollo": "pollo",
        "cosce di pollo": "pollo",
        "petto pollo": "pollo",
        "petto di tacchino": "tacchino",
        "petto tacchino": "tacchino",
        "pane integrale": "pane",
        "pane bianco": "pane",
        "panino": "pane",
        "rosetta": "pane",
        "carne di manzo": "manzo",
        "carne bovina": "manzo",
        "carne di maiale": "maiale",
        "carne suina": "maiale",
        "latte scremato": "latte",
        "latte parzialmente scremato": "latte",
        "latte intero": "latte",
        "yogurt greco": "yogurt",
        "yogurt magro": "yogurt",
        "riso basmati": "riso",
        "riso integrale": "riso integrale",
    }
    for ph, repl in phrase_map.items():
        if ph in s:
            s = s.replace(ph, repl)

    # stopwords comuni
    stop = [
        "il", "lo", "la", "i", "gli", "le",
        "un", "una", "uno",
        "di", "del", "della", "dello", "delle", "dei", "degli",
        "al", "allo", "alla", "alle", "col", "con",
        "e", "ed",
        "alla", "alle", "allo",
        "alla", "alla", "ai", "agli"
    ]

    parola_map = {
        # pomodori "grandi"
        "pomodori": "pomodoro",
        "pomodoro": "pomodoro",

        # piccoli pomodori / ciliegini / datterini
        "pomodorini": "pomodorini",
        "pomodorino": "pomodorini",
        "ciliegini": "pomodorini",
        "ciliegino": "pomodorini",
        "datterini": "pomodorini",
        "datterino": "pomodorini",
        "piccadilly": "pomodorini",

        # pasta (formati)
        "penne": "pasta",
        "spaghetti": "pasta",
        "fusilli": "pasta",
        "farfalle": "pasta",
        "rigatoni": "pasta",
        "linguine": "pasta",
        "tagliatelle": "pasta",
        "maccheroni": "pasta",

        # proteine
        "uova": "uovo",
        "uovo": "uovo",
        "bistecca": "manzo",
        "hamburger": "manzo",
        "cotoletta": "maiale",

        # verdure
        "zucchine": "zucchina",
        "zucchina": "zucchina",
        "melanzane": "melanzana",
        "melanzana": "melanzana",
        "carote": "carota",
        "carota": "carota",
        "cipolle": "cipolla",
        "cipolla": "cipolla",
        "patate": "patata",
        "patata": "patata",

        # condimenti
        "olio": "olio extravergine di oliva",
        "olio extravergine": "olio extravergine di oliva",
        "burro": "burro",
        "sale": "sale",
        "zucchero": "zucchero",

        # latticini
        "mozzarella": "mozzarella",
        "fiordilatte": "mozzarella",
        "scamorza": "scamorza",
        "ricotta": "ricotta",

        # vari
        "pasta": "pasta",
        "pane": "pane",
        "riso": "riso",
    }

    tokens = []
    for token in s.split():
        if token in stop:
            continue
        # mapping parola → canonico
        if token in parola_map:
            tokens.append(parola_map[token])
        else:
            # fallback semplice: togli 'i'/'e' finali (plurali) se ha senso
            if token.endswith("i") or token.endswith("e"):
                base = token[:-1]
                tokens.append(base)
            else:
                tokens.append(token)

    s_norm = " ".join(tokens).strip()
    return s_norm


def normalizza_nome_piatto(nome: str) -> str:
    """
    Per i piatti usiamo la stessa normalizzazione degli alimenti,
    così 'pasta al pomodoro' e 'spaghetti al pomodoro' si avvicinano.
    """
    return normalizza_nome_alimento_py(nome)


def normalizza_unita(q):
    """Converte kg/g/mg/L/ml in grammi. ml≈g per semplicità."""
    if isinstance(q, (int, float)):
        return float(q)
    if not isinstance(q, str):
        return 0.0

    s = q.lower().strip()
    import re
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", s)
    if not m:
        return 0.0

    num = float(m.group(1))

    if "kg" in s:
        return num * 1000.0
    if "mg" in s:
        return num / 1000.0
    if "ml" in s:
        return num
    if "l" in s:
        return num * 1000.0
    if "g" in s:
        return num

    return num


def stima_fattore_scala(q_input, ricetta):
    """Scala la ricetta rispetto al peso totale del piatto."""
    base_peso = float(ricetta.get("peso_totale_piatto_g", 300.0) or 300.0)
    q_norm = normalizza_unita(q_input)
    if q_norm <= 0:
        return 1.0
    return q_norm / base_peso


def get_kcal_ingrediente(nome, quantita_g):
    """
    Calcola le kcal partendo da FoodData_Central.json (kcal/100g).
    Usa prima match esatto, poi fuzzy match sulla colonna 'nome'.
    """
    nome_norm = normalizza_nome_alimento_py(nome)
    if not nome_norm or quantita_g <= 0:
        return 0.0

    # 1) match esatto
    for item in NUTRIENT_DB:
        n_item = (item.get("nome") or "").lower().strip()
        if n_item == nome_norm:
            kcal100 = float(item.get("kcal_100g", 0) or 0)
            return (quantita_g * kcal100) / 100.0

    # 2) fuzzy match (se non trovato esatto)
    best_item = None
    best_score = 0.0
    for item in NUTRIENT_DB:
        n_item = (item.get("nome") or "").lower().strip()
        if not n_item:
            continue
        score = difflib.SequenceMatcher(None, nome_norm, n_item).ratio()
        if score > best_score:
            best_score = score
            best_item = item

    if best_item is not None and best_score >= 0.7:
        kcal100 = float(best_item.get("kcal_100g", 0) or 0)
        return (quantita_g * kcal100) / 100.0

    return 0.0


def trova_ricetta(alimento_raw: str):
    """
    Cerca una ricetta tra:
      1) USER_RECIPES
      2) ITALIAN_RECIPES
    usando:
      - match chiave diretto (nome → nome_con_underscore)
      - match parziale
      - fuzzy match (similar_text like)
    """
    alimento_norm = normalizza_nome_piatto(alimento_raw)
    if not alimento_norm:
        return None, None

    key_norm = alimento_norm.replace(" ", "_")

    sorgenti = [("user", USER_RECIPES), ("base", ITALIAN_RECIPES)]

    # 1) match diretto su chiave normalizzata
    for source_name, src in sorgenti:
        if key_norm in src:
            return src[key_norm], source_name

    # 2) match parziale su chiave
    for source_name, src in sorgenti:
        for k, rec in src.items():
            if alimento_norm in k.replace("_", " "):
                return rec, source_name

    # 3) fuzzy match su chiave
    best_rec = None
    best_src = None
    best_score = 0.0
    for source_name, src in sorgenti:
        for k, rec in src.items():
            label = k.replace("_", " ")
            score = difflib.SequenceMatcher(None, alimento_norm, label).ratio()
            if score > best_score:
                best_score = score
                best_rec = rec
                best_src = source_name

    if best_rec is not None and best_score >= 0.7:
        return best_rec, best_src

    return None, None


def costruisci_ricetta_semplice(alimento_raw: str, quantita: str):
    """
    Se non troviamo la ricetta nel JSON,
    proviamo a creare un piatto semplice monocomponente usando FoodData_Central.
    Esempio: “mela”, “pollo”, “riso”, ecc.
    """
    alimento_norm = normalizza_nome_alimento_py(alimento_raw)
    if not alimento_norm:
        return None

    q_g = normalizza_unita(quantita)
    if q_g <= 0:
        q_g = 100.0  # fallback 100 g

    kcal_tot = get_kcal_ingrediente(alimento_norm, q_g)
    if kcal_tot <= 0:
        # non abbiamo info nutrizionali affidabili
        return None

    ricetta = {
        "titolo": alimento_raw.strip().capitalize() or alimento_norm.capitalize(),
        "peso_totale_piatto_g": q_g,
        "ingredienti": [
            {
                "nome": alimento_norm,
                "quantita_g": q_g
            }
        ]
    }
    return ricetta


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
# ENDPOINT RICETTE (SIMPLE DEMO)
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
        {
            "titolo": "Pasta al pomodoro",
            "ingredienti": "pasta,pomodoro,olio,basilico",
            "tempo": "15",
            "descrizione": "Classico primo piatto"
        },
        {
            "titolo": "Insalata mista",
            "ingredienti": "lattuga,pomodoro,olio,aceto",
            "tempo": "10",
            "descrizione": "Fresca e leggera"
        }
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
# ENDPOINT MEAL (EVOLUTO)
# ===============================
@app.route("/ai/meal", methods=["POST"])
@require_api_key
def ai_meal():
    data = request.get_json(force=True)
    alimento_raw = (data.get("alimento", "") or "").strip()
    quantita = data.get("quantita", "0")
    porzioni = float(data.get("porzioni", 1) or 1)

    if not alimento_raw:
        return jsonify({"error": "ALIMENTO_VUOTO"}), 400

    # 1) cerca ricetta in base + user
    ricetta, sorgente = trova_ricetta(alimento_raw)
    new_recipe = False

    # 2) se non trovata, prova a costruire ricetta semplice da NUTRIENT_DB
    if ricetta is None:
        ricetta = costruisci_ricetta_semplice(alimento_raw, quantita)
        if ricetta is not None:
            # salviamo in USER_RECIPES per usi futuri
            key = normalizza_nome_piatto(alimento_raw).replace(" ", "_")
            if key:
                USER_RECIPES[key] = ricetta
                save_user_recipes()
                sorgente = "user"
                new_recipe = True

    # 3) se ancora nulla → errore (PHP userà fallback interno)
    if ricetta is None:
        return jsonify({"error": "RICETTA_NON_TROVATA"}), 404

    # 4) calcola fattore scala
    fattore = stima_fattore_scala(quantita, ricetta)

    ingredienti_finali = []
    kcal_tot = 0.0

    for ing in ricetta.get("ingredienti", []):
        try:
            nome_raw = ing.get("nome", "")
            base_q = float(ing.get("quantita_g", 0) or 0)
        except Exception:
            continue

        q_finale = base_q * fattore * porzioni
        if q_finale <= 0:
            continue

        # normalizzo il nome dell'ingrediente per allinearlo alla dispensa
        nome_norm = normalizza_nome_alimento_py(nome_raw)

        kcal_ing = get_kcal_ingrediente(nome_norm, q_finale)
        kcal_tot += kcal_ing

        ingredienti_finali.append({
            "nome": nome_norm or nome_raw,
            "quantita_g": round(q_finale, 1),
            "kcal": round(kcal_ing, 1)
        })

    return jsonify({
        "titolo": ricetta.get("titolo", alimento_raw),
        "alimento_originale": alimento_raw,
        "porzioni": porzioni,
        "fattore_scala": round(fattore, 3),
        "sorgente": sorgente or "sconosciuta",
        "new_recipe": new_recipe,
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
        from chat import (
            recupera_memoria,
            genera_risposta_locale,
            salva_conversazione
        )
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
