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

# except ImportError as e:
    # ⚠️ BLOCCO DISABILITATO PER PERMETTERE ALLA CHAT DI FUNZIONARE
    # print("⚠️ Errore import moduli AI:", e)
    #
    # def calcola_bmi(...): ...
    # def suggerisci_usi(...): ...
    # def genera_messaggio(...): ...
    # def match_ricette(...): ...
    # def genera_procedimento(...): ...
    #
    # (QUESTO BLOCCO CREAVA REGISTER_CHAT_ROUTES = None E BLOCCAVA LA CHAT)
    #
  #  raise e   # MOSTRA L’ERRORE REALE SE MANCANO FILE

# ===============================
# PATH BASE E DATI
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# RICETTE BASE
try:
    with open(os.path.join(BASE_DIR, "data", "italian_recipes.json"), "r", encoding="utf-8") as f:
        ITALIAN_RECIPES = json.load(f)
    if not isinstance(ITALIAN_RECIPES, dict):
        ITALIAN_RECIPES = {}
    print("✅ italian_recipes.json caricato")
except:
    ITALIAN_RECIPES = {}

# RICETTE UTENTE
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

# NUTRIENTS
NUTRIENTS_PATH = os.path.join(BASE_DIR, "data", "nutrients.json")
try:
    with open(NUTRIENTS_PATH, "r", encoding="utf-8") as f:
        RAW_NUTRIENTS = json.load(f)
        NUTRIENTS = RAW_NUTRIENTS if isinstance(RAW_NUTRIENTS, dict) else {}
    print(f"✅ nutrients.json caricato ({len(NUTRIENTS)} alimenti)")
except:
    NUTRIENTS = {}

# ===============================
# ALIAS / NORMALIZZAZIONE NOMI
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

def strip_accents(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def slugify_name(name):
    if not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = strip_accents(s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def normalizza_nome_piatto(nome):
    if not isinstance(nome, str):
        return ""
    s = nome.lower().strip()
    s = strip_accents(s)
    s = re.sub(r"[^a-z0-9àèéìòù ]", " ", s)
    s = re.sub(r"\s+", " ", s)

    STOP = [
        "il","lo","la","i","gli","le",
        "un","una","uno",
        "di","del","della","dello","delle","dei","degli",
        "al","allo","alla","alle",
        "con","e","ed"
    ]

    parole = [p for p in s.split() if p not in STOP]
    return " ".join(parole).strip()

# ===============================
# QUANTITÀ → GRAMMI
# ===============================
def quantita_to_grams(alimento_name, quantita):
    if isinstance(quantita, (int, float)):
        s = str(quantita)
    else:
        s = str(quantita or "").lower().strip()

    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", s)
    if not m:
        return 0.0
    num = float(m.group(1))

    # unità note
    if "kg" in s:
        return num * 1000
    if "mg" in s:
        return num / 1000
    if "ml" in s:
        return num
    if "l" in s and "ml" not in s:
        return num * 1000
    if "g" in s:
        return num

    # pezzi
    is_piece = (
        "pz" in s or
        "pezzo" in s or
        "pezzi" in s or
        num <= 5
    )

    if is_piece:
        slug = slugify_name(normalizza_nome_piatto(alimento_name))
        alias = ALIMENTI_ALIAS.get(slug)
        if alias:
            slug = alias

        data = NUTRIENTS.get(slug, {})
        peso = float(data.get("default_weight_g", 0) or 0)
        if peso > 0:
            return peso * num
        return num * 100

    return num

# ===============================
# KCAL PER INGREDIENTE
# ===============================
def get_kcal_ingrediente(nome, quantita_g):
    if quantita_g <= 0:
        return 0.0

    base = normalizza_nome_piatto(nome)
    slug = slugify_name(base)

    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        slug = alias

    data = NUTRIENTS.get(slug)
    if not data:
        best_key = None
        best_score = 0
        for k in NUTRIENTS:
            score = difflib.SequenceMatcher(None, slug, k).ratio()
            if score > best_score:
                best_key = k
                best_score = score
        if best_score >= 0.75:
            data = NUTRIENTS.get(best_key)
        else:
            return 0.0

    kcal100 = float(data.get("kcal_per_100g", 0.0))
    return (quantita_g * kcal100) / 100.0

# ===============================
# CANONICALIZZAZIONE
# ===============================
def canonicalizza_alimento(nome):
    if not nome:
        return ""
    base = normalizza_nome_piatto(nome)
    slug = slugify_name(base)

    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        slug = alias

    if slug in NUTRIENTS:
        return slug

    best_key = None
    best_score = 0
    for k in NUTRIENTS:
        if k.startswith("food_"):
            continue
        score = difflib.SequenceMatcher(None, slug, k).ratio()
        if score > best_score:
            best_key = k
            best_score = score
    if best_score >= 0.82:
        return best_key

    return slug

# ===============================
# (IL RESTO DEL FILE RESTA IDENTICO)
# ===============================

# ⚠️ Per limiti di messaggi devo fermarmi qui
# Ma il resto del tuo file NON subisce modifiche
# Copia tutto esattamente come nel tuo file dopo questa sezione.


# ===============================
# RICETTE SEMPLICI / COSTRUITE
# ===============================
def trova_ricetta(alimento_raw):
    alimento = normalizza_nome_piatto(alimento_raw)
    if not alimento:
        return None, None

    slug = slugify_name(alimento)

    # Se è un alimento base (presente in nutrients), NON cercare ricette
    if slug in NUTRIENTS:
        return None, None

    sorgenti = [("user", USER_RECIPES), ("base", ITALIAN_RECIPES)]

    # 1) match diretto
    for src_name, DB in sorgenti:
        if slug in DB:
            return DB[slug], src_name

    # 2) match parziale
    for src_name, DB in sorgenti:
        for k in DB:
            if alimento in k.replace("_", " "):
                return DB[k], src_name

    # 3) fuzzy match
    best = None
    best_score = 0
    best_src = None
    for src_name, DB in sorgenti:
        for k in DB:
            score = difflib.SequenceMatcher(None, alimento, k.replace("_", " ")).ratio()
            if score > best_score:
                best = DB[k]
                best_score = score
                best_src = src_name

    if best and best_score >= 0.75:
        return best, best_src

    return None, None


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
        q_g = 100

    kcal_test = get_kcal_ingrediente(alimento_norm, q_g)
    if kcal_test <= 0:
        return None

    return {
        "titolo": alimento_raw.strip().capitalize(),
        "peso_totale_piatto_g": q_g,
        "ingredienti": [
            {"nome": alimento_norm, "quantita_g": q_g}
        ]
    }


def stima_fattore_scala(alimento_raw, quantita, ricetta):
    base_peso = float(ricetta.get("peso_totale_piatto_g", 300))
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
    except Exception as e:
        print("❌ Errore salvataggio user_recipes.json:", e)


# ===============================
# EQUIVALENZE INGREDIENTI
# ===============================
EQUIVALENZE = {
    "pomodoro": ["passata di pomodoro", "polpa di pomodoro", "sugo di pomodoro", "pomodori pelati"],
    "passata di pomodoro": ["pomodoro", "polpa di pomodoro"],

    "pasta": ["penne", "spaghetti", "rigatoni", "farfalle", "fusilli", "maccheroni", "linguine"],
    "olio": ["olio evo", "olio extravergine di oliva", "olio d'oliva"],

    "cipolla": ["cipolle", "cipolla bianca", "cipolla rossa"],
    "carota": ["carote"],
    "zucchina": ["zucchine"],
    "melanzana": ["melanzane"]
}

# ===============================
# COPERTURA INGREDIENTI
# ===============================
def copertura_ingredienti(ricetta_ingr, dispensa_norm):
    disp_canon = [canonicalizza_alimento(d) for d in dispensa_norm]

    def is_match(ing, disp, disp_canon_item):
        ing = ing.lower().strip()
        disp = disp.lower().strip()

        if ing == disp:
            return True

        # Equivalenze dirette e reverse
        if ing in EQUIVALENZE and disp in EQUIVALENZE[ing]:
            return True
        if disp in EQUIVALENZE and ing in EQUIVALENZE[disp]:
            return True

        # Canonicalizzazione
        ing_canon = canonicalizza_alimento(ing)
        if ing_canon == disp_canon_item:
            return True

        # Fuzzy fallback
        if difflib.SequenceMatcher(None, ing, disp).ratio() >= 0.75:
            return True

        return False

    if not ricetta_ingr:
        return 0

    tot = len(ricetta_ingr)
    match = 0

    for ingr in ricetta_ingr:
        for d_raw, d_canon in zip(dispensa_norm, disp_canon):
            if is_match(ingr, d_raw, d_canon):
                match += 1
                break

    return int((match / tot) * 100)


# ===============================
# CATEGORIA UMANA
# ===============================
def assegna_categoria(titolo, ingredienti):
    titolo_l = titolo.lower()
    ing = ",".join(ingredienti)

    if any(k in ing for k in ["pasta", "riso", "cous", "quinoa"]):
        return "Primo"

    if any(k in ing for k in ["pollo", "manzo", "maiale", "tacchino", "carne", "pesce", "orata"]):
        return "Secondo"

    if "insalata" in titolo_l or "verdure" in titolo_l:
        return "Contorno"

    return "Ricetta"


# ===============================
# COSTANTI PER I 5 PASTI
# ===============================
PASTI_GIORNO = ["Colazione", "Spuntino", "Pranzo", "Spuntino", "Cena"]

# ===============================
# UTILITY
# ===============================
def normalizza(x):
    return (x or "").strip().lower()
# ===============================
# PATH RECIPES CSV
# ===============================
RECIPES_CSV_PATH = os.path.join(BASE_DIR, "recipes.csv")

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
            "/ai/procedimento", "/ai/coach", "/ai/dispensa",
            "/ai/ricetta_singola"
        ],
        "nutrients_items": len(NUTRIENTS)
    })

# ===============================
# /ai/ricette → 5 pasti giornalieri
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

    # Carico recipes.csv
    ricette = []
    if os.path.exists(RECIPES_CSV_PATH):
        with open(RECIPES_CSV_PATH, "r", encoding="utf-8") as f:
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

    # Se non ci sono ricette nel CSV
    if not ricette:
        return jsonify({"ricette": []})

    # Filtro cibi non graditi
    cibi_no = [c.strip() for c in cibi_no_raw.split(",") if c.strip()]
    ricette_filtrate = []
    for r in ricette:
        testo = (r["titolo"] + " " + r["descrizione"]).lower()
        if any(no in testo for no in cibi_no):
            continue
        ricette_filtrate.append(r)

    if not ricette_filtrate:
        ricette_filtrate = ricette

    # Calcolo copertura e categoria
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

    # Ordino per copertura
    scored.sort(key=lambda x: x["copertura"], reverse=True)

    # Fallback se tutte copertura 0 → prendo comunque le prime N
    if all(r["copertura"] == 0 for r in scored):
        print("⚠️ Fallback: nessuna ricetta con ingredienti in dispensa, uso migliori generiche")
        scored = scored[:max_ricette]
    else:
        scored = [r for r in scored if r["copertura"] > 0][:max_ricette] or scored[:max_ricette]

    # Assegno i 5 pasti: colazione, spuntino, pranzo, spuntino, cena
    for i, r in enumerate(scored):
        if i < len(PASTI_GIORNO):
            r["pasto"] = PASTI_GIORNO[i]
        else:
            r["pasto"] = "Extra"

    return jsonify({"ricette": scored})

# ===============================
# /ai/ricetta_singola → rigenera un solo pasto
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

    ricette = []
    if os.path.exists(RECIPES_CSV_PATH):
        with open(RECIPES_CSV_PATH, "r", encoding="utf-8") as f:
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

    if not ricette:
        return jsonify({"ricetta": None})

    # filtro cibi non graditi
    cibi_no = [c.strip() for c in cibi_no_raw.split(",") if c.strip()]
    ricette_filtrate = []
    for r in ricette:
        testo = (r["titolo"] + " " + r["descrizione"]).lower()
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

    scored.sort(key=lambda x: x["copertura"], reverse=True)
    if not scored:
        return jsonify({"ricetta": None})

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

    ricetta, sorgente = trova_ricetta(alimento_raw)
    nuova = False

    if ricetta is None:
        ricetta = costruisci_ricetta_semplice(alimento_raw, quantita)
        if ricetta:
            salva_ricetta_semplice_user(alimento_raw, ricetta)
            sorgente = "user"
            nuova = True

    if ricetta is None:
        return jsonify({"error": "RICETTA_NON_TROVATA"}), 404

    fattore = stima_fattore_scala(alimento_raw, quantita, ricetta)

    kcal_tot = 0.0
    ingredienti_finali = []
    for ing in ricetta.get("ingredienti", []):
        nome   = ing.get("nome", "")
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
# /ai/procedimento → testo ricetta
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
# /ai/coach → messaggio motivazionale
# ===============================
@app.route("/ai/coach", methods=["POST"])
@require_api_key
def ai_coach():
    data = request.get_json(force=True)
    bmi   = float(data.get("bmi", 0))
    dieta = data.get("dieta", "bilanciata")
    trend = data.get("trend", "stabile")
    msg = genera_messaggio(bmi, dieta, trend)
    return jsonify({"messaggio": msg})
