from flask import Flask, request, jsonify
import pandas as pd
import os
from functools import wraps
from flask_cors import CORS
import json
import difflib
import unicodedata
import re
import csv
import random

# ===============================
# MODULI LOCALI (IMPORT PRINCIPALI)
# ===============================
try:
    from nutrition_ai import calcola_bmi
    from dispensa_ai import suggerisci_usi
    from coach import genera_messaggio
    from utils import match_ricette, genera_procedimento
    from chat import register_chat_routes
    print("✅ Moduli AI caricati correttamente.")
except ImportError as e:
    print("⚠️ Errore import moduli AI:", e)

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
            {"titolo": "Pasta al pomodoro", "ingredienti": ["pasta", "pomodoro", "olio"], "tempo": "15 min",
             "descrizione": "Classico primo piatto italiano."},
            {"titolo": "Insalata mista", "ingredienti": ["lattuga", "pomodoro", "olio"], "tempo": "10 min",
             "descrizione": "Fresca e leggera."}
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

    register_chat_routes = None


# ===============================
# PATH BASE E DATI
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------- RICETTE BASE -------
try:
    with open(os.path.join(BASE_DIR, "data", "italian_recipes.json"), "r", encoding="utf-8") as f:
        ITALIAN_RECIPES = json.load(f)
    if not isinstance(ITALIAN_RECIPES, dict):
        ITALIAN_RECIPES = {}
    print("✅ italian_recipes.json caricato")
except:
    ITALIAN_RECIPES = {}

# ------- RICETTE UTENTE -------
USER_RECIPES_PATH = os.path.join(BASE_DIR, "data", "user_recipes.json")
try:
    if os.path.exists(USER_RECIPES_PATH):
        with open(USER_RECIPES_PATH, "r", encoding="utf-8") as f:
            USER_RECIPES = json.load(f)
        if not isinstance(USER_RECIPES, dict):
            USER_RECIPES = {}
    else:
        USER_RECIPES = {}
    print("✅ user_recipes.json caricato")
except:
    USER_RECIPES = {}

# ------- NUTRITION DATA -------
NUTRIENTS_PATH = os.path.join(BASE_DIR, "data", "nutrients.json")
try:
    with open(NUTRIENTS_PATH, "r", encoding="utf-8") as f:
        RAW_NUTRIENTS = json.load(f)
        NUTRIENTS = RAW_NUTRIENTS if isinstance(RAW_NUTRIENTS, dict) else {}
    print(f"✅ nutrients.json caricato ({len(NUTRIENTS)} alimenti)")
except:
    NUTRIENTS = {}
# ===============================
# ALIAS ALIMENTI
# ===============================
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

# ===============================
# FUNZIONI BASE DI NORMALIZZAZIONE
# ===============================
def strip_accents(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def slugify_name(name):
    """Converte 'Passata di pomodoro' → 'passata_di_pomodoro'."""
    if not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = strip_accents(s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def normalizza_nome_piatto(nome: str) -> str:
    """Normalizza nomi alimenti/pietanze per fuzzy match."""
    if not isinstance(nome, str):
        return ""
    s = nome.lower().strip()
    s = strip_accents(s)
    s = re.sub(r"[^a-z0-9àèéìòù ]", " ", s)
    s = re.sub(r"\s+", " ", s)

    STOP = [
        "il", "lo", "la", "i", "gli", "le",
        "un", "una", "uno",
        "di", "del", "della", "dello", "delle", "dei", "degli",
        "al", "allo", "alla", "alle",
        "con", "e", "ed"
    ]
    parole = [p for p in s.split() if p not in STOP]
    return " ".join(parole).strip()

def normalizza(nome):
    return (nome or "").strip().lower()

# ===============================
# CONVERSIONE QUANTITÀ → GRAMMI
# ===============================
def quantita_to_grams(alimento_name, quantita):
    """Interpreta '1 kg', '200 g', '2 pz', '3', ecc. in grammi."""
    if isinstance(quantita, (int, float)):
        s = str(quantita)
    else:
        s = str(quantita or "").lower().strip()

    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", s)
    if not m:
        return 0.0
    num = float(m.group(1))

    # unità esplicite
    if "kg" in s:
        return num * 1000
    if "mg" in s:
        return num / 1000
    if "ml" in s:
        return num          # approx liquidi = gr
    if "l" in s and "ml" not in s:
        return num * 1000
    if "g" in s:
        return num

    # pezzi → cerca peso da nutrients.json
    is_piece = ("pz" in s or "pezzo" in s or "pezzi" in s or num <= 5)
    if is_piece:
        slug = slugify_name(normalizza_nome_piatto(alimento_name))
        alias = ALIMENTI_ALIAS.get(slug)
        if alias:
            slug = alias

        data = NUTRIENTS.get(slug, {})
        peso_default = float(data.get("default_weight_g", 0) or 0)

        if peso_default > 0:
            return peso_default * num

        return num * 100  # fallback

    # nessuna unità → interpreto come grammi
    return num

# ===============================
# KCAL PER INGREDIENTE
# ===============================
def get_kcal_ingrediente(nome, quantita_g):
    """Calcola le kcal usando nutrients.json + fuzzy fallback."""
    if quantita_g <= 0:
        return 0.0

    base = normalizza_nome_piatto(nome)
    slug = slugify_name(base)

    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        slug = alias

    data = NUTRIENTS.get(slug)
    if not data:
        # fuzzy match
        best_key, best_score = None, 0
        for k in NUTRIENTS.keys():
            score = difflib.SequenceMatcher(None, slug, k).ratio()
            if score > best_score:
                best_score, best_key = score, k
        if best_key and best_score >= 0.75:
            data = NUTRIENTS[best_key]
        else:
            return 0.0

    kcal100 = float(data.get("kcal_per_100g", 0.0))
    return (quantita_g * kcal100) / 100.0

# ===============================
# CANONICALIZZAZIONE INGREDIENTI
# ===============================
def canonicalizza_alimento(nome: str) -> str:
    """Usa alias + nutrients + fuzzy per un nome uniforme."""
    if not nome:
        return ""
    base = normalizza_nome_piatto(nome)
    slug = slugify_name(base)

    # alias
    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        slug = alias

    # match diretto
    if slug in NUTRIENTS:
        return slug

    # fuzzy
    best_key, best_score = None, 0
    for k in NUTRIENTS.keys():
        if k.startswith("food_"):
            continue
        score = difflib.SequenceMatcher(None, slug, k).ratio()
        if score > best_score:
            best_key, best_score = k, score

    if best_key and best_score >= 0.82:
        return best_key

    return slug

# ===============================
# COSTRUZIONE RICETTA SEMPLICE
# ===============================
def costruisci_ricetta_semplice(alimento_raw, quantita):
    alimento_norm = normalizza_nome_piatto(alimento_raw)
    if not alimento_norm:
        return None

    slug = slugify_name(alimento_norm)
    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        alimento_norm = alias.replace("_", " ")

    q_g = quantita_to_grams(alimento_norm, quantita)
    if q_g <= 0:
        q_g = 100.0

    kcal_test = get_kcal_ingrediente(alimento_norm, q_g)
    if kcal_test <= 0:
        kcal_test = get_kcal_ingrediente(alimento_raw, q_g)
        if kcal_test <= 0:
            return None

    return {
        "titolo": alimento_raw.strip().capitalize(),
        "peso_totale_piatto_g": q_g,
        "ingredienti": [
            {"nome": alimento_norm, "quantita_g": q_g}
        ]
    }

# ===============================
# FATTORI DI SCALA
# ===============================
def stima_fattore_scala(alimento_raw, quantita, ricetta):
    base_peso = float(ricetta.get("peso_totale_piatto_g", 300) or 300)
    richiesti = quantita_to_grams(alimento_raw, quantita)

    if richiesti <= 0 or base_peso <= 0:
        return 1.0

    return richiesti / base_peso

def salva_ricetta_semplice_user(alimento_raw, ricetta):
    key = slugify_name(alimento_raw)
    if not key or not ricetta:
        return

    USER_RECIPES[key] = ricetta
    try:
        with open(USER_RECIPES_PATH, "w", encoding="utf-8") as f:
            json.dump(USER_RECIPES, f, ensure_ascii=False, indent=2)
        print("💾 user_recipes.json aggiornato")
    except:
        pass
# ===============================
# EQUIVALENZE AVANZATE INGREDIENTI
# ===============================
EQUIVALENZE = {
    "pomodoro": ["passata di pomodoro", "polpa di pomodoro", "pomodori pelati", "sugo di pomodoro"],
    "passata di pomodoro": ["pomodoro", "polpa di pomodoro", "pomodori pelati"],
    "pasta": ["penne", "spaghetti", "rigatoni", "farfalle", "fusilli", "maccheroni", "linguine"],
    "olio": ["olio extravergine di oliva", "olio evo", "olio d'oliva"],
    "cipolla": ["cipolle", "cipolla bianca", "cipolla rossa", "cipolla dorata"],
    "carota": ["carote"],
    "zucchina": ["zucchine"],
    "melanzana": ["melanzane"],
}

# ===============================
# COPERTURA INGREDIENTI DISPENSA
# ===============================
def copertura_ingredienti(ricetta_ingr, dispensa_norm):
    """
    Percentuale di ingredienti della ricetta coperti da ciò che ho in dispensa usando:
    - match diretto
    - equivalenze
    - canonicalizzazione nutrients
    - fuzzy match
    """
    dispensa_canon = [canonicalizza_alimento(d) for d in dispensa_norm]

    def is_match(ing, disp_raw, disp_canon):
        ing = ing.lower().strip()
        disp_raw = disp_raw.lower().strip()

        # diretto
        if ing == disp_raw:
            return True

        # equivalenze forward + reverse
        if ing in EQUIVALENZE and disp_raw in EQUIVALENZE[ing]:
            return True
        for k, lista in EQUIVALENZE.items():
            if ing == k and disp_raw in lista:
                return True
            if disp_raw == k and ing in lista:
                return True

        # canonical
        ing_canon = canonicalizza_alimento(ing)
        if ing_canon == disp_canon:
            return True

        # fuzzy
        if difflib.SequenceMatcher(None, ing, disp_raw).ratio() >= 0.75:
            return True

        return False

    if not ricetta_ingr:
        return 0

    match = 0
    for ing in ricetta_ingr:
        for d_raw, d_canon in zip(dispensa_norm, dispensa_canon):
            if is_match(ing, d_raw, d_canon):
                match += 1
                break

    return int((match / len(ricetta_ingr)) * 100)


# ===============================
# CATEGORIZZAZIONE AUTOMATICA PIATTI
# ===============================
def assegna_categoria(titolo, ingredienti):
    titolo_l = titolo.lower()
    ing = ",".join(ingredienti)

    if any(k in ing for k in ["pasta", "riso", "gnocchi", "cous", "quinoa"]):
        return "Primo"

    if any(k in ing for k in ["pollo", "manzo", "maiale", "tacchino", "carne", "bistecca", "orata", "spigola", "pesce", "branzino"]):
        return "Secondo"

    if "insalata" in titolo_l or "verdure" in titolo_l or "zucchine" in ing:
        return "Contorno"

    return "Ricetta"


# ===============================
# DEFINIZIONE 5 PASTI GIORNALIERI
# ===============================
PASTI_GIORNO = [
    "Colazione",
    "Spuntino mattina",
    "Pranzo",
    "Spuntino pomeriggio",
    "Cena"
]


# ===============================
# ENDPOINT PRINCIPALE: /ai/ricette
# ===============================
@app.route("/ai/ricette", methods=["POST"])
def ai_ricette():
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)

    dieta           = data.get("dieta", "Mediterranea")
    cibi_no_raw     = (data.get("cibi_non_graditi") or "").lower()
    dispensa        = data.get("dispensa", [])
    max_ricette_req = int(data.get("max_ricette", 5))
    max_ricette     = max(1, min(5, max_ricette_req))

    dispensa_norm = [normalizza(x) for x in dispensa]

    # ========== CARICO CSV RECIPES ==========
    csv_path = os.path.join(BASE_DIR, "recipes.csv")
    ricette = []
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                titolo = (row.get("titolo") or "").strip()
                ingr   = (row.get("ingredienti") or "").strip()
                tempo  = (row.get("tempo") or "").strip()
                descr  = (row.get("descrizione") or "").strip()

                if titolo and ingr:
                    ingredienti = [i.strip().lower() for i in ingr.split(",") if i.strip()]
                    ricette.append({
                        "titolo": titolo,
                        "ingredienti": ingredienti,
                        "tempo": tempo,
                        "descrizione": descr
                    })

    # ========== FILTRO CIBI NON GRADITI ==========
    cibi_no = [c.strip() for c in cibi_no_raw.split(",") if c.strip()]

    ricette_filtrate = []
    for r in ricette:
        testo = (r["descrizione"] + " " + r["titolo"]).lower()
        if any(no in testo for no in cibi_no):
            continue
        ricette_filtrate.append(r)

    if not ricette_filtrate:
        ricette_filtrate = ricette  # fallback

    # ========== CALCOLO COPERTURA ==========
    scored = []
    for r in ricette_filtrate:
        cop = copertura_ingredienti(r["ingredienti"], dispensa_norm)

        scored.append({
            "titolo": r["titolo"],
            "ingredienti": r["ingredienti"],
            "tempo": r["tempo"],
            "descrizione": r["descrizione"],
            "copertura": cop,
            "categoria": assegna_categoria(r["titolo"], r["ingredienti"])
        })

    # Ordino per copertura (ingredienti disponibili)
    scored.sort(key=lambda x: x["copertura"], reverse=True)

    # ========== FALLBACK SE NESSUNA HA COPERTURA > 0 ==========
    if all(r["copertura"] == 0 for r in scored):
        print("⚠️ Fallback attivo: nessuna ricetta trovata con ingredienti in dispensa.")
        scored = scored[:max_ricette]  # prendo le migliori anche se 0%

    # ========== LIMITO A 5 PASTI ==========
    scored = scored[:max_ricette]

    # ========== ASSEGNO RUOLO PASTO ==========
    for i, r in enumerate(scored):
        if i < len(PASTI_GIORNO):
            r["pasto"] = PASTI_GIORNO[i]
        else:
            r["pasto"] = "Extra"

    return jsonify({"ricette": scored})
# ===============================
# FLASK BASE + CORS
# ===============================
app = Flask(__name__)
CORS(app, resources={r"/ai/*": {"origins": "*"}}, supports_credentials=False)

# Registra le rotte Chat AI solo se disponibili
if 'register_chat_routes' in globals() and register_chat_routes:
    register_chat_routes(app)
else:
    print("⚠️ Chat AI non attiva: register_chat_routes non trovato")

# ===============================
# API KEY E VERIFICA
# ===============================
API_KEY = os.getenv(
    "AI_KEY",
    "gofoody_3f8G7pLzR!x2N9tQ@uY5aWsE#jD6kHrV^m1ZbTqL4cP0oFi"
)

def verifica_chiave():
    """Controlla l’API KEY nelle chiamate lato app PHP."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.replace("Bearer ", "").strip()
    return token == API_KEY

def require_api_key(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "API_KEY mancante"}), 401
        token = auth.replace("Bearer ", "").strip()
        if token != API_KEY:
            return jsonify({"error": "API_KEY errata"}), 403
        return f(*args, **kwargs)
    return wrap

# ===============================
# HEALTH CHECK
# ===============================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "AI online ✅",
        "message": "Flask funziona correttamente.",
        "routes": [
            "/ai/meal", "/ai/nutrizione", "/ai/ricette",
            "/ai/procedimento", "/ai/coach", "/ai/dispensa", "/ai/ricetta_singola"
        ],
        "nutrients_items": len(NUTRIENTS)
    })

# ===============================
# /ai/ricetta_singola → rigenera UN solo pasto
# ===============================
@app.route("/ai/ricetta_singola", methods=["POST"])
def ai_ricetta_singola():
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    dieta       = data.get("dieta", "Mediterranea")
    cibi_no_raw = (data.get("cibi_non_graditi") or "").lower()
    dispensa    = data.get("dispensa", [])
    pasto       = data.get("pasto", "")

    if not pasto:
        return jsonify({"error": "Missing 'pasto'"}), 400

    dispensa_norm = [normalizza(x) for x in dispensa]

    # Carico CSV ricette
    csv_path = os.path.join(BASE_DIR, "recipes.csv")
    ricette = []
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                titolo = (row.get("titolo") or "").strip()
                ingr   = (row.get("ingredienti") or "").strip()
                tempo  = (row.get("tempo") or "").strip()
                descr  = (row.get("descrizione") or "").strip()

                if titolo and ingr:
                    ingredienti = [i.strip().lower() for i in ingr.split(",") if i.strip()]
                    ricette.append({
                        "titolo": titolo,
                        "ingredienti": ingredienti,
                        "tempo": tempo,
                        "descrizione": descr
                    })

    # filtro cibi non graditi
    cibi_no = [c.strip() for c in cibi_no_raw.split(",") if c.strip()]
    ricette_filtrate = []
    for r in ricette:
        testo = (r["descrizione"] + " " + r["titolo"]).lower()
        if any(no in testo for no in cibi_no):
            continue
        ricette_filtrate.append(r)

    if not ricette_filtrate:
        ricette_filtrate = ricette

    scored = []
    for r in ricette_filtrate:
        cop = copertura_ingredienti(r["ingredienti"], dispensa_norm)
        scored.append({
            "titolo": r["titolo"],
            "ingredienti": r["ingredienti"],
            "tempo": r["tempo"],
            "descrizione": r["descrizione"],
            "copertura": cop,
            "categoria": assegna_categoria(r["titolo"], r["ingredienti"]),
            "pasto": pasto
        })

    # Ordino per copertura
    scored.sort(key=lambda x: x["copertura"], reverse=True)

    if not scored:
        return jsonify({"ricetta": None})

    # se tutte copertura 0, prendo comunque la migliore
    scelta = scored[0]
    return jsonify({"ricetta": scelta})

# ===============================
# /ai/meal → tasto "Ho mangiato qualcosa"
# ===============================
@app.route("/ai/meal", methods=["POST"])
@require_api_key
def ai_meal():
    data = request.get_json(force=True)

    alimento_raw = (data.get("alimento", "") or "").strip()
    quantita     = data.get("quantita", "0")
    porzioni     = float(data.get("porzioni", 1) or 1)

    if not alimento_raw:
        return jsonify({"error": "ALIMENTO_VUOTO"}), 400

    # 1) Provo a trovare ricetta complessa (italian_recipes / user_recipes)
    def trova_ricetta(alimento_raw):
        alimento = normalizza_nome_piatto(alimento_raw)
        if not alimento:
            return None, None

        slug = slugify_name(alimento)

        # se è un alimento base in NUTRIENTS → niente ricetta complessa
        if slug in NUTRIENTS:
            return None, None

        sorgenti = [("user", USER_RECIPES), ("base", ITALIAN_RECIPES)]

        # match diretto
        for src_name, DB in sorgenti:
            if slug in DB:
                return DB[slug], src_name

        # match parziale
        for src_name, DB in sorgenti:
            for k in DB:
                if alimento in k.replace("_", " "):
                    return DB[k], src_name

        # fuzzy
        best, best_score, best_src = None, 0.0, None
        for src_name, DB in sorgenti:
            for k in DB:
                score = difflib.SequenceMatcher(
                    None, alimento, k.replace("_", " ")
                ).ratio()
                if score > best_score:
                    best_score, best, best_src = score, DB[k], src_name

        if best and best_score >= 0.75:
            return best, best_src or "fuzzy"

        return None, None

    ricetta, sorgente = trova_ricetta(alimento_raw)
    nuova = False

    # 2) Se non trovata, costruisco ricetta semplice monocomponente
    if ricetta is None:
        ricetta = costruisci_ricetta_semplice(alimento_raw, quantita)
        if ricetta:
            salva_ricetta_semplice_user(alimento_raw, ricetta)
            sorgente = "user"
            nuova = True

    if ricetta is None:
        return jsonify({"error": "RICETTA_NON_TROVATA"}), 404

    # 3) Calcolo fattore di scala rispetto alla quantità richiesta
    fattore = stima_fattore_scala(alimento_raw, quantita, ricetta)

    kcal_tot = 0.0
    ingredienti_finali = []

    for ing in ricetta.get("ingredienti", []):
        nome    = ing.get("nome", "")
        base_q  = float(ing.get("quantita_g", 0) or 0)
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
        "new_recipe": nuova,
        "ingredienti": ingredienti_finali,
        "kcal_totali": round(kcal_tot, 1)
    })

# ===============================
# /ai/nutrizione → BMI
# ===============================
@app.route("/ai/nutrizione", methods=["POST"])
@require_api_key
def ai_nutrizione():
    data = request.get_json(force=True)

    peso    = float(data.get("peso", 0))
    altezza = float(data.get("altezza", 0))
    eta     = int(data.get("eta", 0))
    sesso   = data.get("sesso", "N/D")

    risultato = calcola_bmi(peso, altezza, eta, sesso)
    return jsonify(risultato)

# ===============================
# /ai/dispensa → avvisi anti-spreco
# ===============================
@app.route("/ai/dispensa", methods=["POST"])
@require_api_key
def ai_dispensa():
    data = request.get_json(force=True)
    dispensa = data.get("dispensa", [])
    risultati = suggerisci_usi(dispensa)
    return jsonify({"alert": risultati})

# ===============================
# /ai/procedimento → testo ricetta step-by-step
# ===============================
@app.route("/ai/procedimento", methods=["POST"])
@require_api_key
def ai_procedimento():
    data = request.get_json(force=True)
    titolo = data.get("titolo", "") or ""
    ingredienti = data.get("ingredienti", []) or []
    dieta = data.get("dieta", "") or ""

    if not isinstance(ingredienti, list):
        ingredienti = [str(ingredienti)]

    testo = genera_procedimento(titolo, ingredienti, dieta)
    return jsonify({"procedimento": testo})

# ===============================
# /ai/coach (opzionale, se usi il coach motivazionale)
# ===============================
@app.route("/ai/coach", methods=["POST"])
@require_api_key
def ai_coach():
    data = request.get_json(force=True)
    bmi    = float(data.get("bmi", 0))
    dieta  = data.get("dieta", "bilanciata")
    trend  = data.get("trend", "stabile")
    msg = genera_messaggio(bmi, dieta, trend)
    return jsonify({"messaggio": msg})
