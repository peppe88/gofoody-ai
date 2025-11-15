from flask import Flask, request, jsonify
import pandas as pd
import os
from functools import wraps
from flask_cors import CORS
import json
import difflib
import unicodedata
import re
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
# PATH BASE E DATI
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------- RICETTE BASE (italian_recipes.json) -------
try:
    with open(os.path.join(BASE_DIR, "data", "italian_recipes.json"), "r", encoding="utf-8") as f:
        ITALIAN_RECIPES = json.load(f)
    if not isinstance(ITALIAN_RECIPES, dict):
        ITALIAN_RECIPES = {}
    print("✅ italian_recipes.json caricato")
except Exception as e:
    print("❌ Errore caricamento italian_recipes.json:", e)
    ITALIAN_RECIPES = {}

# ------- RICETTE UTENTE (user_recipes.json) -------
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

# ------- DATABASE NUTRIZIONALE (nutrients.json) -------
NUTRIENTS_PATH = os.path.join(BASE_DIR, "data", "nutrients.json")
try:
    if os.path.exists(NUTRIENTS_PATH):
        with open(NUTRIENTS_PATH, "r", encoding="utf-8") as f:
            RAW_NUTRIENTS = json.load(f)
        if isinstance(RAW_NUTRIENTS, dict):
            NUTRIENTS = RAW_NUTRIENTS
        else:
            NUTRIENTS = {}
    else:
        NUTRIENTS = {}
    print(f"✅ nutrients.json caricato ({len(NUTRIENTS)} alimenti)")
except Exception as e:
    print("❌ Errore caricamento nutrients.json:", e)
    NUTRIENTS = {}


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
# FUNZIONI DI NORMALIZZAZIONE
# ===============================
def strip_accents(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def slugify_name(name: str) -> str:
    # Mappa alias per alimenti base (singolare/plurale/sinonimi)
# Chiavi e valori sono nello stesso formato di slugify_name()
ALIMENTI_ALIAS = {
    "mele": "mela",
    "mela_rossa": "mela",
    "mela_verde": "mela",

    "banane": "banana",
    "pere": "pera",
    "arance": "arancia",
    "pesche": "pesca",
    "ciliegie": "ciliegia",

    "pomodori": "pomodoro",
    "pomodorini": "pomodoro",
    "ciliegini": "pomodoro",
    "datterini": "pomodoro",

    "zucchine": "zucchina",
    "melanzane": "melanzana",
    "carote": "carota",
    "cipolle": "cipolla",

    "uova": "uovo",

    "penne": "pasta_secca",
    "spaghetti": "pasta_secca",
    "fusilli": "pasta_secca",
    "rigatoni": "pasta_secca",
    "farfalle": "pasta_secca",
}
    """
    Converte 'Passata di pomodoro' → 'passata_di_pomodoro'
    ed è la chiave usata in nutrients.json.
    """
    if not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = strip_accents(s)
    import re
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def normalizza_nome_piatto(nome: str) -> str:
    """Normalizza il nome del piatto per matchare ricette."""
    if not isinstance(nome, str):
        return ""
    s = nome.strip().lower()
    s = strip_accents(s)

    import re
    s = re.sub(r"[^a-z0-9àèéìòù ]", " ", s)
    s = re.sub(r"\s+", " ", s)

    stop = [
        "il", "lo", "la", "i", "gli", "le",
        "un", "una", "uno",
        "di", "del", "della", "dello", "delle", "dei", "degli",
        "al", "allo", "alla", "alle", "col", "con",
        "e", "ed"
    ]
    parole = [p for p in s.split(" ") if p not in stop]
    s = " ".join(parole).strip()
    return s


def normalizza_unita(q):
    def quantita_to_grams(alimento_name: str, quantita) -> float:
    """
    Converte la quantità inserita dall'utente in grammi, usando anche default_weight_g
    di nutrients.json quando l'utente indica pezzi (pz / pezzo / pezzi / numero piccolo).
    """
    # Normalizzo la stringa
    if isinstance(quantita, (int, float)):
        s = str(quantita)
    else:
        s = (quantita or "").lower().strip()

    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", s)
    if not m:
        return 0.0

    num = float(m.group(1))

    # Unità di peso esplicite
    if "kg" in s:
        return num * 1000.0
    if "mg" in s:
        return num / 1000.0
    if "ml" in s:
        return num               # 1 ml ≈ 1 g
    if "l" in s and "ml" not in s:
        return num * 1000.0
    if "g" in s:
        return num

    # Se non c'è nessuna unità di peso, capiamo se sono PEZZI
    is_piece = (
        "pz" in s or
        "pezzo" in s or
        "pezzi" in s or
        " x" in s or
        (num <= 5 and float(num).is_integer())
    )

    if is_piece:
        # Provo a prendere default_weight_g da nutrients.json
        base_norm = normalizza_nome_piatto(alimento_name)
        slug = slugify_name(base_norm)

        alias = ALIMENTI_ALIAS.get(slug)
        if alias:
            slug = alias

        data = NUTRIENTS.get(slug, {})
        default_w = float(data.get("default_weight_g", 0.0) or 0.0)
        if default_w <= 0:
            default_w = 100.0  # fallback ragionevole

        return num * default_w

    # Nessuna unità → interpreto come grammi
    return num
    """Converte kg/g/mg/L/ml in grammi. (ml≈g per semplicità)"""
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
        return num * 1000
    if "mg" in s:
        return num / 1000
    if "ml" in s:
        return num   # approssimazione 1ml≈1g
    if "l" in s and "ml" not in s:
        return num * 1000
    if "g" in s:
        return num

    return num


# ===============================
# FUNZIONI NUTRIZIONALI
# ===============================
def get_kcal_ingrediente(nome: str, quantita_g: float) -> float:
    """
    Calcola le kcal di un ingrediente usando nutrients.json.
    Usa alias (mela/mele, pomodorini/pomodoro, ecc.).
    """
    if quantita_g <= 0:
        return 0.0

    # Normalizzo il nome e applico alias
    base_norm = normalizza_nome_piatto(nome)
    slug = slugify_name(base_norm)

    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        slug = alias

    data = NUTRIENTS.get(slug)
    if not data:
        # Ultimo tentativo: fuzzy match sull'etichetta
        best_key = None
        best_score = 0.0
        for k, v in NUTRIENTS.items():
            label = v.get("label", k)
            score = difflib.SequenceMatcher(
                None,
                slugify_name(nome),
                slugify_name(label)
            ).ratio()
            if score > best_score:
                best_score = score
                best_key = k

        if best_key and best_score >= 0.75:
            data = NUTRIENTS[best_key]
        else:
            return 0.0

    kcal_100 = float(data.get("kcal_per_100g", 0.0))
    return (quantita_g * kcal_100) / 100.0

def stima_fattore_scala(alimento_raw, quantita, ricetta):
    """
    Scala la ricetta rispetto al peso totale del piatto.
    Per piatti composti (italian_recipes / user_recipes):
      fattore = grammi_richiesti / peso_totale_piatto
    Per alimenti semplici (mela, banana, ecc.) la ricetta viene costruita
    già con il peso richiesto, quindi il fattore tipicamente è 1.
    """
    base_peso = float(ricetta.get("peso_totale_piatto_g", 300) or 300)
    q_norm = quantita_to_grams(alimento_raw, quantita)
    if q_norm <= 0 or base_peso <= 0:
        return 1.0
    return q_norm / base_peso

def trova_ricetta(alimento_raw: str):
    """
    Cerca una ricetta tra:
      1) USER_RECIPES
      2) ITALIAN_RECIPES

    MA se l'alimento è presente in nutrients.json (es. 'mela', 'banana'),
    lo trattiamo come alimento semplice → nessuna ricetta predefinita.
    """
    alimento_norm = normalizza_nome_piatto(alimento_raw)
    if not alimento_norm:
        return None, None

    key_norm = slugify_name(alimento_norm)

    # Se è un alimento base (presente in nutrients.json) → niente ricetta,
    # useremo costruisci_ricetta_semplice()
    if key_norm in NUTRIENTS:
        return None, None

    sorgenti = [("user", USER_RECIPES), ("base", ITALIAN_RECIPES)]

    # 1) match diretto chiave
    for source_name, src in sorgenti:
        if key_norm in src:
            return src[key_norm], source_name

    # 2) match parziale su chiave
    for source_name, src in sorgenti:
        for k, rec in src.items():
            label_k = k.replace("_", " ")
            if alimento_norm in label_k:
                return rec, source_name

    # 3) fuzzy match
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

def costruisci_ricetta_semplice(alimento_raw: str, quantita):
    """
    Per alimenti semplici (es. 'mela', '100 g pollo')
    crea una ricetta monocomponente usando nutrients.json.
    Usa quantita_to_grams per gestire g, kg, ml, pz, ecc.
    """
    alimento_norm = normalizza_nome_piatto(alimento_raw)
    if not alimento_norm:
        return None

    # Applico eventuali alias per nomi come "mele" -> "mela"
    slug = slugify_name(alimento_norm)
    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        # trasformo "mela" in "mela" (da slug) per coerenza con nutrients
        alimento_norm = alias.replace("_", " ")

    q_g = quantita_to_grams(alimento_norm, quantita)
    if q_g <= 0:
        q_g = 100.0  # fallback

    # Verifico che esista un alimento corrispondente in nutrients
    kcal_test = get_kcal_ingrediente(alimento_norm, q_g)
    if kcal_test <= 0:
        # ultimo tentativo con il raw name
        kcal_test = get_kcal_ingrediente(alimento_raw, q_g)
        if kcal_test <= 0:
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

def salva_ricetta_semplice_user(alimento_raw: str, ricetta: dict):
    """
    Salva la ricetta semplice in USER_RECIPES,
    così la volta dopo /ai/meal la trova al volo.
    """
    key = slugify_name(alimento_raw)
    if not key or not ricetta:
        return
    USER_RECIPES[key] = ricetta
    save_user_recipes()


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
        ],
        "nutrients_items": len(NUTRIENTS)
    })


# ===============================
# ENDPOINT RICETTE (SUGGERIMENTI)
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
# ENDPOINT MEAL (NUOVO, SOLIDO)
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

    # 2) se non trovata, prova a costruire ricetta semplice
    if ricetta is None:
        ricetta = costruisci_ricetta_semplice(alimento_raw, quantita)
        if ricetta is not None:
            salva_ricetta_semplice_user(alimento_raw, ricetta)
            sorgente = "user"
            new_recipe = True

    if ricetta is None:
        # qui PHP userà il suo fallback interno
        return jsonify({"error": "RICETTA_NON_TROVATA"}), 404

    # 3) calcola fattore scala
    fattore = stima_fattore_scala(alimento_raw, quantita, ricetta)

    ingredienti_finali = []
    kcal_tot = 0.0

    for ing in ricetta.get("ingredienti", []):
        nome = ing.get("nome", "")
        base_q = float(ing.get("quantita_g", 0) or 0)
        if base_q <= 0:
            continue

        q_finale = base_q * fattore * porzioni
        if q_finale <= 0:
            continue

        kcal_ing = get_kcal_ingrediente(nome, q_finale)
        kcal_tot += kcal_ing

        ingredienti_finali.append({
            "nome": nome,
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
# ENDPOINT NUTRIZIONE (BMI)
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
# ENDPOINT DISPENSA (AVVISI)
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
