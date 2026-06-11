from flask import Flask, jsonify
import pandas as pd

app = Flask(__name__)

def load_csv(name):
    try:
        df = pd.read_csv(f"out/{name}")
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

@app.route("/baseline")
def baseline():
    return jsonify(load_csv("baseline_vs_nota.csv"))

@app.route("/force-update")
def force_update():
    return jsonify(load_csv("force_update_vs_nota_media.csv"))

@app.route("/tendencia")
def tendencia():
    return jsonify(load_csv("tendencia_diaria.csv"))


import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
