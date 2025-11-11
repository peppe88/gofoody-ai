from datetime import datetime

def calcola_bmi(peso, altezza, eta, sesso):
    """
    Calcola il BMI e restituisce una valutazione con suggerimento nutrizionale.
    """
    if altezza <= 0 or peso <= 0:
        return {
            "bmi": None,
            "categoria": "Dati non validi",
            "suggerimento": "Inserisci peso e altezza per calcolare il tuo BMI."
        }

    altezza_m = altezza / 100  # conversione in metri
    bmi = round(peso / (altezza_m ** 2), 1)

    # Classificazione standard OMS
    if bmi < 18.5:
        categoria = "Sottopeso"
        emoji = "🥗"
        suggerimento = "Aumenta l’apporto calorico con pasti nutrienti e regolari."
    elif bmi < 25:
        categoria = "Peso ideale"
        emoji = "💪"
        suggerimento = "Mantieni il tuo stile di vita equilibrato e attivo!"
    elif bmi < 30:
        categoria = "Sovrappeso"
        emoji = "⚖️"
        suggerimento = "Riduci zuccheri e grassi, punta su pasti più leggeri."
    else:
        categoria = "Obesità"
        emoji = "🚨"
        suggerimento = "Consulta un nutrizionista per un piano alimentare bilanciato."

    # Personalizzazione in base all’età
    if eta and eta > 55 and bmi < 20:
        suggerimento += " Dopo i 55 anni, un BMI leggermente più alto può essere fisiologico."
    if sesso.lower().startswith("f") and bmi < 18.5:
        suggerimento += " Assicurati di avere un apporto proteico adeguato."

    risultato = {
        "bmi": bmi,
        "categoria": categoria,
        "emoji": emoji,
        "suggerimento": suggerimento
    }
    return risultato