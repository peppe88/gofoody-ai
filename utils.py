import random

def normalizza_testo(testo):
    """Pulisce e normalizza una stringa per confronti"""
    if not testo:
        return ""
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


def genera_procedimento(titolo, ingredienti, dieta):
    """
    Genera un procedimento testuale plausibile per la ricetta.
    """
    if not ingredienti:
        return "Nessun ingrediente specificato. Non è possibile generare il procedimento."

    intro = [
        f"Iniziamo a preparare {titolo.lower()}, una ricetta {dieta.lower() if dieta else 'semplice'}!",
        f"Oggi cuciniamo {titolo.lower()}, con un tocco sano e gustoso.",
        f"Prepariamo insieme {titolo.lower()}, usando ingredienti freschi e genuini."
    ]

    steps = [
        f"1️⃣ Prepara {', '.join(ingredienti[:3])} tagliandoli in modo uniforme.",
        f"2️⃣ Scalda una padella o pentola con un filo d’olio e aggiungi gli ingredienti principali.",
        f"3️⃣ Cuoci a fuoco medio per {random.randint(10, 25)} minuti mescolando di tanto in tanto.",
        f"4️⃣ Aggiungi sale, spezie e condimenti secondo la tua dieta {dieta.lower() if dieta else 'personale'}.",
        f"5️⃣ Servi la tua {titolo.lower()} calda o fredda, a piacere. Buon appetito! 🍽️"
    ]

    return "\n".join([random.choice(intro)] + steps)