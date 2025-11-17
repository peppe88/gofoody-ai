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
    """Normalizza il nome del piatto per match/ricerca."""
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


# ===============================
# QUANTITÀ → GRAMMI
# ===============================
def quantita_to_grams(alimento_name, quantita):
    """
    Converte input (es. '1 kg', '200 g', '2 pz') in grammi.
    Usa default_weight_g da nutrients.json per i pezzi, quando disponibile.
    """
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
        return num           # approx 1 ml ≈ 1 g
    if "l" in s and "ml" not in s:
        return num * 1000
    if "g" in s:
        return num

    # pezzi (pz / pezzo / pezzi / numeri piccoli senza unità)
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
        peso_default = float(data.get("default_weight_g", 0) or 0)

        if peso_default > 0:
            return peso_default * num

        # fallback: 1 pezzo ≈ 100 g
        return num * 100

    # nessuna unità → interpreto come grammi
    return num


# ===============================
# KCAL PER INGREDIENTE
# ===============================
def get_kcal_ingrediente(nome, quantita_g):
    """
    Calcola le kcal per un ingrediente usando nutrients.json.
    Usa alias (mela/mele, pomodorini/pomodoro, ecc.) e fuzzy-match di fallback.
    """
    if quantita_g <= 0:
        return 0.0

    base = normalizza_nome_piatto(nome)
    slug = slugify_name(base)

    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        slug = alias

    data = NUTRIENTS.get(slug)
    if not data:
        # fuzzy fallback sullo slug
        best_key = None
        best_score = 0.0
        for k, v in NUTRIENTS.items():
            score = difflib.SequenceMatcher(None, slug, k).ratio()
            if score > best_score:
                best_score = score
                best_key = k
        if best_key and best_score > 0.75:
            data = NUTRIENTS[best_key]
        else:
            return 0.0

    kcal100 = float(data.get("kcal_per_100g", 0.0))
    return (quantita_g * kcal100) / 100.0


# ===============================
# FUNZIONI RICETTE BASE / SEMPLICI
# ===============================
def trova_ricetta(alimento_raw):
    """
    Cerca una ricetta tra:
      - USER_RECIPES (create dall'utente/app)
      - ITALIAN_RECIPES (base)
    Se l'alimento è presente in NUTRIENTS come alimento semplice,
    NON ritorna una ricetta (verrà usata la ricetta semplice).
    """
    alimento = normalizza_nome_piatto(alimento_raw)
    if not alimento:
        return None, None

    slug = slugify_name(alimento)

    # Se è un alimento base (presente nel DB nutrizionale) → niente ricetta predefinita
    if slug in NUTRIENTS:
        return None, None

    sorgenti = [("user", USER_RECIPES), ("base", ITALIAN_RECIPES)]

    # 1) match diretto sulla chiave
    for src_name, DB in sorgenti:
        if slug in DB:
            return DB[slug], src_name

    # 2) match parziale sul nome
    for src_name, DB in sorgenti:
        for k in DB:
            if alimento in k.replace("_", " "):
                return DB[k], src_name

    # 3) fuzzy match sul nome
    best = None
    best_score = 0.0
    best_src = None
    for src_name, DB in sorgenti:
        for k in DB:
            score = difflib.SequenceMatcher(
                None,
                alimento,
                k.replace("_", " ")
            ).ratio()
            if score > best_score:
                best_score = score
                best = DB[k]
                best_src = src_name

    if best and best_score >= 0.75:
        return best, best_src or "fuzzy"

    return None, None


def costruisci_ricetta_semplice(alimento_raw, quantita):
    """
    Se non esiste una ricetta composta, costruisce una ricetta semplice monocomponente
    usando nutrients.json (es. 'mela', 'banana', '100 g pollo' ecc.).
    """
    alimento_norm = normalizza_nome_piatto(alimento_raw)
    if not alimento_norm:
        return None

    slug = slugify_name(alimento_norm)
    alias = ALIMENTI_ALIAS.get(slug)
    if alias:
        alimento_norm = alias.replace("_", " ")

    q_g = quantita_to_grams(alimento_norm, quantita)
    if q_g <= 0:
        q_g = 100.0  # fallback

    kcal_test = get_kcal_ingrediente(alimento_norm, q_g)
    if kcal_test <= 0:
        kcal_test = get_kcal_ingrediente(alimento_raw, q_g)
        if kcal_test <= 0:
            return None

    return {
        "titolo": alimento_raw.strip().capitalize() or alimento_norm.capitalize(),
        "peso_totale_piatto_g": q_g,
        "ingredienti": [
            {
                "nome": alimento_norm,
                "quantita_g": q_g
            }
        ]
    }


def stima_fattore_scala(alimento_raw, quantita, ricetta):
    """
    Scala la ricetta rispetto al peso totale del piatto.
    Per piatti composti:
      fattore = grammi_richiesti / peso_totale_piatto
    Per alimenti semplici:
      il peso_totale_piatto_g è già impostato alla quantità richiesta → fattore ~1.
    """
    base_peso = float(ricetta.get("peso_totale_piatto_g", 300) or 300)
    richiesti = quantita_to_grams(alimento_raw, quantita)
    if richiesti <= 0 or base_peso <= 0:
        return 1.0
    return richiesti / base_peso


def salva_ricetta_semplice_user(alimento_raw, ricetta):
    """
    Salva la ricetta semplice in USER_RECIPES, così /ai/meal è più veloce
    le volte successive.
    """
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
# VERIFICA API KEY USATA PER /ai/ricette
# ===============================
def verifica_chiave():
    """Controlla l’API KEY nella chiamata lato app PHP."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.replace("Bearer ", "").strip()
    return token == API_KEY


# ===============================
# RICETTE CSV
# ===============================
RECIPES_CSV_PATH = os.path.join(BASE_DIR, "recipes.csv")

def load_recipes_csv():
    ricette = []
    try:
        with open(RECIPES_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                titolo = (row.get("titolo") or "").strip()
                ingr   = (row.get("ingredienti") or "").strip()
                tempo  = (row.get("tempo") or "").strip()
                descr  = (row.get("descrizione") or "").strip()

                if titolo and ingr:
                    ingredienti = [
                        i.strip().lower()
                        for i in ingr.split(",")
                        if i.strip()
                    ]

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
    return (nome or "").strip().lower()


# ===============================
# COPERTURA INGREDIENTI DISPENSA
# ===============================
def copertura_ingredienti(ricetta_ingr, dispensa_norm):
    tot = len(ricetta_ingr)
    if tot == 0:
        return 0

    match = sum(1 for ingr in ricetta_ingr if ingr in dispensa_norm)
    return int((match / tot) * 100)


# ===============================
# CATEGORIZZAZIONE AUTOMATICA PIATTI
# ===============================
def assegna_categoria(titolo, ingredienti):
    titolo_l = titolo.lower()
    ing = ",".join(ingredienti)

    if any(k in ing for k in ["pasta", "riso", "cous", "quinoa"]):
        return "Primo"
    if any(k in ing for k in ["orata", "pollo", "manzo", "maiale", "tacchino", "carne", "pesce"]):
        return "Secondo"
    if "insalata" in titolo_l or "verdure" in titolo_l or "grigliate" in titolo_l:
        return "Contorno"
    return "Ricetta"


GIORNI_SETTIMANA = [
    "Lunedì", "Martedì", "Mercoledì",
    "Giovedì", "Venerdì", "Sabato", "Domenica"
]


# ===============================
# /ai/ricette  → CUORE DEL SISTEMA MENU SETTIMANALE
# ===============================
@app.route("/ai/ricette", methods=["POST"])
def ai_ricette():
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)

    dieta           = data.get("dieta", "Mediterranea")
    cibi_no_raw     = (data.get("cibi_non_graditi") or "").lower()
    dispensa        = data.get("dispensa", [])
    max_ricette     = int(data.get("max_ricette", 7))  # default 7 (1 per giorno)

    # Normalizza dispensa
    dispensa_norm = [normalizza(x) for x in dispensa]

    # Carica database CSV
    tutte = load_recipes_csv()

    if not tutte:
        return jsonify({"ricette": []})

    dieta_norm = dieta.lower()
    filtrate = []

    # ===============================
    # FILTRO DIETA
    # ===============================
    for r in tutte:
        ing = r["ingredienti"]

        if dieta_norm == "vegana":
            if any(i in [
                "uova", "latte", "formaggio", "burro", "yogurt",
                "mozzarella", "tonno", "pesce", "carne", "pollo",
                "tacchino", "manzo", "maiale"
            ] for i in ing):
                continue

        elif dieta_norm == "vegetariana":
            if any(i in [
                "carne", "pollo", "tacchino", "maiale", "manzo",
                "orata", "tonno", "pesce"
            ] for i in ing):
                continue

        # Mediterranea → tutti i piatti ok
        filtrate.append(r)

    # ===============================
    # FILTRO CIBI NON GRADITI
    # ===============================
    if cibi_no_raw.strip():
        blocchi = [normalizza(x) for x in cibi_no_raw.split(",") if x.strip()]

        filtrate = [
            r for r in filtrate
            if not any(
                b in r["titolo"].lower() or b in ",".join(r["ingredienti"])
                for b in blocchi
            )
        ]

    # Fallback → almeno qualcosa
    if not filtrate:
        filtrate = tutte

    # ===============================
    # CALCOLO COPERTURA DISPENSA + CATEGORIA
    # ===============================
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

    # Ordino per copertura (ingredienti disponibili)
    ricette_fin.sort(key=lambda x: x["copertura"], reverse=True)

    # Prendo max N
    ricette_fin = ricette_fin[:max_ricette]

    # ===============================
    # ASSEGNAZIONE GIORNI DELLA SETTIMANA
    # ===============================
    giorni = GIORNI_SETTIMANA.copy()
    random.shuffle(giorni)

    for i, r in enumerate(ricette_fin):
        r["giorno"] = giorni[i % len(giorni)]

    return jsonify({"ricette": ricette_fin})
# ===============================
# FLASK BASE
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
            "/ai/procedimento", "/ai/coach", "/ai/dispensa", "/ai/chat"
        ],
        "nutrients_items": len(NUTRIENTS)
    })


# ===============================
# ENDPOINT MEAL (calcolo kcal piatto)
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
# ENDPOINT NUTRIZIONE (BMI)
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
# ENDPOINT DISPENSA (AVVISI ANTI-SPRECO)
# ===============================
@app.route("/ai/dispensa", methods=["POST"])
@require_api_key
def ai_dispensa():
    data = request.get_json(force=True)
    dispensa = data.get("dispensa", [])
    risultati = suggerisci_usi(dispensa)
    return jsonify({"alert": risultati})
