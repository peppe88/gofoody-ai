from datetime import datetime, timedelta

def suggerisci_usi(dispensa):
    """
    Analizza una lista di alimenti e restituisce suggerimenti su cosa consumare prima.
    
    Parametri:
        dispensa: elenco di dizionari, es.
        [
            {"nome": "Pomodori", "scadenza": "2025-11-13"},
            {"nome": "Latte", "scadenza": "2025-11-12"},
            {"nome": "Pasta", "scadenza": ""}
        ]
    """
    oggi = datetime.now().date()
    suggerimenti = []
    
    for item in dispensa:
        nome = item.get("nome", "").capitalize().strip()
        scad_str = item.get("scadenza", "").strip()
        if not scad_str:
            continue
        
        try:
            data_scad = datetime.strptime(scad_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        giorni = (data_scad - oggi).days
        
        # Analisi temporale
        if giorni < 0:
            suggerimenti.append(f"⚠️ {nome} è scaduto da {-giorni} giorni!")
        elif giorni == 0:
            suggerimenti.append(f"⚠️ {nome} scade OGGI — consumalo subito!")
        elif giorni <= 2:
            suggerimenti.append(f"⏳ {nome} scade tra {giorni} giorni — usalo prima possibile.")
        elif giorni <= 5:
            suggerimenti.append(f"📅 {nome} è da consumare entro {giorni} giorni.")
        else:
            # Nessun alert per alimenti con scadenza lontana
            continue

    if not suggerimenti:
        suggerimenti.append("✅ Tutti gli alimenti in dispensa sono in buono stato.")

    return suggerimenti