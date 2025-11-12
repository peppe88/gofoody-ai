import random
import os
import re
from flask import request, jsonify

# ===========================
# CONFIG SICUREZZA
# ===========================
AI_KEY = os.getenv(
    "AI_KEY",
    "gofoody_3f8G7pLzR!x2N9tQ@uY5aWsE#jD6kHrV^m1ZbTqL4cP0oFi"
)  # stessa chiave PHP e Flask


def verifica_chiave():
    """Verifica che la richiesta contenga la chiave API corretta."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        print("⚠️ Nessuna chiave AI trovata nell'header.")
        return False
    token = auth_header.split(" ")[1]
    valido = token == AI_KEY
    if not valido:
        print("🚫 Chiave AI non valida.")
    return valido


# ===========================
# FUNZIONI DI UTILITÀ
# ===========================
def normalizza_testo(testo):
    """Pulisce e normalizza una stringa per confronti"""
    if not testo:
        return ""
    testo = re.sub(r"[^a-zA-Z0-9àèéìòùç' ]+", "", testo)
    return str(testo).strip().lower()


def match_ricette(recipes_df, dispensa, allergie, preferenze):
    """
    Restituisce un elenco di ricette ordinate per match percentuale
    con la dispensa e filtrate in base alle allergie e preferenze.
    """
    suggerimenti = []

    for _, r in recipes_df.iterrows():
        titolo = r.get("titolo", "")
        descrizione = r.get("descrizione", "")
        tempo = r.get("tempo", "")
        ingredienti_raw = r.get("ingredienti", "")

        # Normalizza ingredienti
        ingredienti = [normalizza_testo(x) for x in ingredienti_raw.split(",") if x.strip()]
        ing_set = set(ingredienti)

        # Calcolo punteggio match
        match = len(dispensa & ing_set) / len(ing_set) if len(ing_set) > 0 else 0

        # Esclusione per allergie
        if ing_set & allergie:
            continue

        # Bonus se la ricetta include preferenze alimentari
        bonus = 0.1 if any(p in descrizione.lower() for p in preferenze) else 0
        punteggio_finale = round(min(1.0, match + bonus), 2)

        if match > 0:
            suggerimenti.append({
                "nome": titolo,
                "match": punteggio_finale,
                "ingredienti": list(ing_set),
                "tempo": tempo,
                "descrizione": descrizione
            })

    # Ordina per punteggio più alto
    suggerimenti.sort(key=lambda x: x["match"], reverse=True)
    return suggerimenti


# ===========================
# GENERATORE PROCEDIMENTO "AI"
# ===========================
def genera_procedimento(titolo, ingredienti, dieta):
    """
    Genera un procedimento testuale realistico per la ricetta,
    in base a ingredienti e dieta, con tono naturale e istruzioni AI-like.
    """
    if not ingredienti:
        return "⚠️ Nessun ingrediente specificato. Non è possibile generare il procedimento."

    titolo = titolo.strip().capitalize()
    dieta_txt = dieta.lower() if dieta else "personale"

    intro_varianti = [
        f"👩‍🍳 Oggi prepariamo *{titolo}*, una ricetta {dieta_txt} piena di sapore e semplicità.",
        f"🍴 Benvenuto in cucina! Creiamo insieme *{titolo}*, perfetta per la tua dieta {dieta_txt}.",
        f"🥗 Iniziamo con *{titolo}*, un piatto genuino e adatto a chi ama mangiare bene!"
    ]
    intro = random.choice(intro_varianti)

    base_steps = [
        f"1️⃣ Prepara con cura {', '.join(ingredienti[:3])}, assicurandoti che siano puliti e tagliati uniformemente.",
        f"2️⃣ In una padella aggiungi un filo d’olio e soffriggi gli ingredienti principali per 2–3 minuti.",
        f"3️⃣ Aggiungi gli altri ingredienti gradualmente, mescolando per ottenere un composto armonioso.",
        f"4️⃣ Lascia cuocere per circa {random.randint(12, 25)} minuti, finché i profumi non riempiono la cucina.",
        f"5️⃣ Aggiusta di sale, erbe e spezie secondo la tua dieta {dieta_txt}.",
        f"6️⃣ Impiatta con cura e servi subito: *{titolo}* è pronto per essere gustato! 😋"
    ]

    bonus_step = ""
    if "pasta" in ingredienti or "riso" in ingredienti:
        bonus_step = "💡 Suggerimento: manteca con un filo d’olio a crudo per una consistenza vellutata."
    elif "carne" in ingredienti or "pollo" in ingredienti:
        bonus_step = "🔥 Per un gusto intenso, lascialo riposare un paio di minuti prima di servire."
    elif "verdure" in ingredienti or "insalata" in titolo.lower():
        bonus_step = "🌿 Aggiungi un tocco di limone o aceto balsamico per esaltarne la freschezza."

    procedimento_finale = "\n".join([intro] + base_steps + ([bonus_step] if bonus_step else []))
    return procedimento_finale


# ===========================
# ENDPOINT (opzionali Flask)
# ===========================
def endpoint_ricette(recipes_df):
    """Gestisce la chiamata /ai/ricetta"""
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    dispensa = set(i.lower() for i in data.get("dispensa", []))
    allergie = set(i.lower() for i in data.get("allergie", []))
    preferenze = set(i.lower() for i in data.get("preferenze", []))

    risultati = match_ricette(recipes_df, dispensa, allergie, preferenze)
    return jsonify({"ricette": risultati[:5]})


def endpoint_procedimento():
    """Gestisce la chiamata /ai/procedimento"""
    if not verifica_chiave():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    titolo = data.get("titolo", "Ricetta")
    ingredienti = data.get("ingredienti", [])
    dieta = data.get("dieta", "")
    testo = genera_procedimento(titolo, ingredienti, dieta)
    return jsonify({"procedimento": testo})
