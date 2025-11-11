import random
from datetime import datetime

def genera_messaggio(bmi, dieta, trend_peso):
    """
    Genera un messaggio motivazionale o nutrizionale in base ai dati dell'utente.

    Parametri:
        bmi (float): indice di massa corporea
        dieta (str): tipo di dieta (es. "Mediterranea", "Vegana")
        trend_peso (str): "aumento", "diminuzione", "stabile"
    """
    ora = datetime.now().hour
    saluto = "Buongiorno" if ora < 12 else ("Buon pomeriggio" if ora < 18 else "Buonasera")

    messaggi_base = [
        "Ricorda di bere abbastanza acqua 💧 e di includere verdure fresche nei tuoi pasti!",
        "Muoviti almeno 30 minuti oggi: anche una passeggiata fa la differenza 🚶‍♀️.",
        "Oggi è un buon giorno per provare una nuova ricetta sana 🌿.",
        "Non saltare i pasti principali: la regolarità aiuta il metabolismo ⚡.",
        "Sorridi 😄 — anche il benessere emotivo fa parte di uno stile di vita sano."
    ]

    # Analisi BMI
    if not bmi or bmi <= 0:
        base = random.choice(messaggi_base)
        return f"{saluto}! {base}"

    if bmi < 18.5:
        frase_bmi = "Il tuo peso è leggermente inferiore alla media 🥗. Aggiungi spuntini sani e nutrienti!"
    elif bmi < 25:
        frase_bmi = "Ottimo equilibrio 💪 — continua così con la tua alimentazione e attività fisica."
    elif bmi < 30:
        frase_bmi = "Attenzione ⚖️ — piccole modifiche alle porzioni possono aiutarti a tornare in forma."
    else:
        frase_bmi = "Obiettivo salute 🚀 — prediligi alimenti freschi, leggeri e ricchi di fibre."

    # Analisi trend peso
    if trend_peso == "diminuzione":
        frase_trend = "Ottimo! Stai migliorando i tuoi parametri, ma mantieni sempre un ritmo sostenibile. 🌿"
    elif trend_peso == "aumento":
        frase_trend = "Il peso è in lieve aumento: rivedi le abitudini e prediligi pasti leggeri oggi. ⚖️"
    else:
        frase_trend = "Stabilità è sinonimo di costanza: continua su questa strada! ✅"

    # Personalizzazione per tipo di dieta
    dieta = (dieta or "").lower()
    if "vegana" in dieta:
        frase_dieta = "Ottima scelta 🌱! Ricorda di integrare vitamina B12 e proteine vegetali."
    elif "vegetariana" in dieta:
        frase_dieta = "Perfetto equilibrio 🌽: abbina legumi e cereali per un pasto completo."
    elif "mediterranea" in dieta:
        frase_dieta = "La dieta Mediterranea è un grande alleato ❤️. Mantieni varietà e porzioni giuste."
    else:
        frase_dieta = "Segui un’alimentazione bilanciata e varia per restare in forma 🌞."

    # Composizione finale
    messaggio_finale = f"{saluto}! {frase_bmi} {frase_trend} {frase_dieta}"
    return messaggio_finale