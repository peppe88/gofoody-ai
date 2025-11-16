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
except Exception as e:
    print("❌ Errore:", e)
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


# ======= ALIAS ALIMENTI =======
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
# FUNZIONI BASE
# ===============================
def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def slugify_name(name):
    if not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = strip_accents(s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def normalizza_nome_piatto(nome: str) -> str:
    if not isinstance(nome, str):
        return ""
    s = nome.lower().strip()
    s = strip_accents(s)
    s = re.sub(r"[^a-z0-9àèéìòù ]", " ", s)
    s = re.sub(r"\s+", " ", s)

    STOP = ["il","lo","la","i","gli","le","un","una","uno","di","del","della","dello",
            "delle","dei","degli","al","allo","alla","alle","con","e","ed"]
    parole = [p for p in s.split() if p not in STOP]

    return " ".join(parole).strip()


# ========= QUANTITÀ → GRAMMI =========
def quantita_to_grams(alimento_name, quantita):
    if isinstance(quantita, (int, float)):
        s = str(quantita)
    else:
        s = str(quantita or "").lower().strip()

    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", s)
    if not m:
        return 0.0
    num = float(m.group(1))

    # unità di peso esplicite
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

        return num * 100

    return num


# ========= KCAL =========
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
        # fuzzy fallback
        best = None
        score_best = 0
        for k, v in NUTRIENTS.items():
            score = difflib.SequenceMatcher(None, slug, k).ratio()
            if score > score_best:
                score_best = score
                best = k
        if best and score_best > 0.75:
            data = NUTRIENTS[best]
        else:
            return 0.0

    kcal100 = float(data.get("kcal_per_100g", 0))
    return (quantita_g * kcal100) / 100


# ============================================
# =============  /ai/ricette  ================
# ============================================
import csv
import random
from flask import jsonify, request

RECIPES_CSV_PATH = "recipes.csv"  # percorso interno

def load_recipes_csv():
    ricette = []
    try:
        with open(RECIPES_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                titolo = row.get("titolo", "").strip()
                ingr   = row.get("ingredienti", "").strip()
                tempo  = row.get("tempo", "").strip()
                descr  = row.get("descrizione", "").strip()

                if titolo and ingr:
                    ingredienti = [i.strip().lower() for i in ingr.split(",") if i.strip()]

                    ricette.append({
                        "titolo": titolo,
                        "ingredienti": ingredienti,
                        "tempo": tempo,
                        "descrizione": descr
                    })
    except Exception as e:
        print("⚠️ Errore lettura recipes.csv:", e)

    return ricette


def normalizza(nome):
    return nome.strip().lower()


def copertura_ingredienti(ricetta_ingr, dispensa_norm):
    tot = len(ricetta_ingr)
    if tot == 0:
        return 0

    match = 0
    for ingr in ricetta_ingr:
        if ingr in dispensa_norm:
            match += 1

    return int((match / tot) * 100)


def assegna_categoria(titolo, ingredienti):
    titolo_l = titolo.lower()
    ing = ",".join(ingredienti)

    if "pasta" in ing or "riso" in ing or "cous" in ing or "quinoa" in ing:
        return "Primo"
    if "orata" in ing or "pollo" in ing or "carne" in ing or "pesce" in ing:
        return "Secondo"
    if "insalata" in titolo_l or "verdure" in titolo_l or "grigliate" in titolo_l:
        return "Contorno"
    return "Ricetta"


GIORNI_SETTIMANA = [
    "Lunedì", "Martedì", "Mercoledì",
    "Giovedì", "Venerdì", "Sabato", "Domenica"
]


@app.route("/ai/ricette", methods=["POST"])
def ai_ricette():
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)

    dieta           = data.get("dieta", "Mediterranea")
    cibi_no_raw     = data.get("cibi_non_graditi", "").lower()
    dispensa        = data.get("dispensa", [])
    max_ricette     = int(data.get("max_ricette", 8))

    # Normalizzazione dispensa
    dispensa_norm = [normalizza(x) for x in dispensa]

    # Carica ricette CSV
    tutte = load_recipes_csv()

    if not tutte:
        return jsonify({"ricette": []})

    # --- FILTRO PER DIETA ---
    dieta_norm = dieta.lower()

    filtrate = []
    for r in tutte:
        ing = r["ingredienti"]

        if dieta_norm == "vegana":
            if any(i in ["uova","latte","formaggio","yogurt","burro","mozzarella","tonno","pesce","carne"] for i in ing):
                continue

        elif dieta_norm == "vegetariana":
            if any(i in ["carne","pollo","tacchino","maiale","manzo","orata","pesce","tonno"] for i in ing):
                continue

        # mediterranea → nessun filtro speciale
        filtrate.append(r)

    # --- FILTRO CIBI NON GRADITI ---
    if cibi_no_raw.strip() != "":
        blocchi = [normalizza(x) for x in cibi_no_raw.split(",")]

        filtrate = [
            r for r in filtrate
            if not any( b in r["titolo"].lower() or b in ",".join(r["ingredienti"]) for b in blocchi )
        ]

    # Se non rimane nulla → fallback
    if not filtrate:
        filtrate = tutte

    # --- CALCOLO COPERTURA DISPONIBILITÀ ---
    ricette_fin = []
    for r in filtrate:
        cop = copertura_ingredienti(r["ingredienti"], dispensa_norm)

        ricette_fin.append({
            "titolo": r["titolo"],
            "ingredienti": r["ingredienti"],
            "tempo": r["tempo"],
            "descrizione": r["descrizione"],
            "copertura": cop,
            "categoria": assegna_categoria(r["titolo"], r["ingredienti"])
        })

    # Ordino: prima le più fattibili
    ricette_fin.sort(key=lambda x: x["copertura"], reverse=True)

    # Taglio al numero richiesto
    ricette_fin = ricette_fin[:max_ricette]

    # Assegna giorni settimana in modo casuale
    giorni = GIORNI_SETTIMANA.copy()
    random.shuffle(giorni)

    for i, r in enumerate(ricette_fin):
        r["giorno"] = giorni[i % 7]

    return jsonify({"ricette": ricette_fin})


# ===============================
# FLASK BASE
# ===============================
app = Flask(__name__)
CORS(app, resources={r"/ai/*": {"origins": "*"}}, supports_credentials=False)

if register_chat_routes:
    register_chat_routes(app)


API_KEY = os.getenv("AI_KEY", "gofoody_3f8G7pLzR!x2N9tQ@uY5aWsE#jD6kHrV^m1ZbTqL4cP0oFi")


def require_api_key(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "API_KEY mancante"}), 401
        if auth.replace("Bearer ", "") != API_KEY:
            return jsonify({"error": "API_KEY errata"}), 403
        return f(*args, **kwargs)
    return wrap


# ===============================
# HEALTH
# ===============================
@app.route("/health")
def health():
    return jsonify({
        "status": "OK",
        "nutrients_items": len(NUTRIENTS)
    })


# ===============================
# AI MEAL
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

    kcal_tot = 0
    ingredienti_finali = []

    for ing in ricetta["ingredienti"]:
        nome = ing["nome"]
        base_q = ing["quantita_g"]
        q_finale = base_q * fattore * porzioni
        kcal_ing = get_kcal_ingrediente(nome, q_finale)
        kcal_tot += kcal_ing

        ingredienti_finali.append({
            "nome": nome,
            "quantita_g": round(q_finale, 1),
            "kcal": round(kcal_ing, 1)
        })

    return jsonify({
        "titolo": ricetta["titolo"],
        "sorgente": sorgente or "sconosciuta",
        "new_recipe": nuova,
        "fattore_scala": round(fattore, 3),
        "ingredienti": ingredienti_finali,
        "kcal_totali": round(kcal_tot, 1)
    })


# ===============================
# BMI
# ===============================
@app.route("/ai/nutrizione", methods=["POST"])
@require_api_key
def ai_nutrizione():
    data = request.get_json(force=True)
    ris = calcola_bmi(
        float(data.get("peso", 0)),
        float(data.get("altezza", 0)),
        int(data.get("eta", 0)),
        data.get("sesso", "N/D")
    )
    return jsonify(ris)


# ===============================
# DISPENSA
# ===============================
@app.route("/ai/dispensa", methods=["POST"])
@require_api_key
def ai_dispensa():
    data = request.get_json(force=True)
    dispensa = data.get("dispensa", [])
    return jsonify({"alert": suggerisci_usi(dispensa)})


# ===============================
# COACH
# ===============================
@app.route("/ai/coach", methods=["POST"])
@require_api_key
def ai_coach():
    data = request.get_json(force=True)
    msg = genera_messaggio(
        data.get("bmi", 0),
        data.get("dieta", ""),
        data.get("trend_peso", "stabile")
    )
    return jsonify({"coach_message": msg})


# ===============================
# CHAT
# ===============================
@app.route("/ai/chat", methods=["POST"])
def ai_chat_direct():
    try:
        from chat import recupera_memoria, genera_risposta_locale, salva_conversazione
    except:
        return jsonify({"risposta": "Errore interno AI."}), 500

    data = request.get_json(force=True) or {}
    prompt = data.get("prompt", "").strip()
    id_utente = int(data.get("id_utente", 0))

    if not prompt:
        return jsonify({"risposta": "Scrivimi qualcosa 😊"})

    memoria = recupera_memoria(id_utente)
    risposta = genera_risposta_locale(prompt, memoria)
    salva_conversazione(id_utente, prompt, risposta)

    return jsonify({"risposta": risposta})


# ===============================
# AVVIO
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
