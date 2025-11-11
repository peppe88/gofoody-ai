# /ai/procedimento_ai.py
from flask import jsonify, request
import random

def genera_procedimento(titolo, ingredienti, dieta):
    steps = [
        "Prepara tutti gli ingredienti e puliscili accuratamente.",
        "Taglia o prepara secondo necessità (verdure, carne, ecc.).",
        "Cuoci in padella o al forno secondo il tipo di ricetta.",
        "Aggiungi condimenti e spezie a piacere.",
        "Servi il piatto con un tocco personale!"
    ]
    procedimento = f"Procedimento per {titolo} ({dieta}):\n"
    procedimento += "\n".join(f"{i+1}. {step}" for i, step in enumerate(random.sample(steps, len(steps))))
    return procedimento

def procedimento_blueprint(app):
    @app.route("/procedimento", methods=["POST"])
    def procedimento():
        data = request.get_json() or {}
        titolo = data.get("titolo", "Ricetta")
        ingredienti = data.get("ingredienti", "")
        dieta = data.get("dieta", "Generica")
        testo = genera_procedimento(titolo, ingredienti, dieta)
        return jsonify({"procedimento": testo})