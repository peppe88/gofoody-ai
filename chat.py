# ================================================================
#  GoFoody AI - chat.py (VERSIONE COMPATIBILE RENDER)
#  Chat locale senza MySQL, sempre attiva
# ================================================================

from flask import request, jsonify
import random

# ================================================================
# RISPOSTE BASE (simil-AI)
# ================================================================

def genera_risposta(prompt):
    p = prompt.lower()

    # Risposte base intelligenti
    if "ciao" in p or "salve" in p:
        return "Ciao 👋! Sono GoFoody AI. Come posso aiutarti oggi?"
    if "ricetta" in p:
        return "Dimmi cosa hai in dispensa e ti suggerisco una ricetta 🍝"
    if "dispensa" in p:
        return "Posso dirti cosa consumare prima per evitare sprechi! 📦"
    if "dieta" in p:
        return "Vuoi suggerimenti per una dieta equilibrata? 🥗"
    if "aiuto" in p or "help" in p:
        return "Eccomi! Dimmi pure cosa ti serve 💡"

    # Risposte casuali
    fallback = [
        "Interessante! Raccontami meglio 😄",
        "Vuoi un consiglio sulla cucina, calorie o ricette? 🍽️",
        "Parlami di cosa hai mangiato o cosa vuoi cucinare!",
        "Sono qui per aiutarti nella cucina di tutti i giorni 👨‍🍳"
    ]

    return random.choice(fallback)


# ================================================================
# REGISTRAZIONE ROTTA
# ================================================================

def register_chat_routes(app):

    @app.route("/ai/chat", methods=["POST"])
    def chat_ai():
        try:
            data = request.get_json(force=True)
            prompt = data.get("prompt", "").strip()
        except:
            return jsonify({"risposta": "Errore nella richiesta."}), 400

        if not prompt:
            return jsonify({"risposta": "Scrivimi un messaggio 😄"})

        risposta = genera_risposta(prompt)
        return jsonify({"risposta": risposta})
