from flask import Blueprint, jsonify
from datetime import date, timedelta
import requests

wordle_bp = Blueprint("wordle", __name__)

@wordle_bp.route("/answer", methods=["GET"])
def get_answer():
    tomorrow = date.today() + timedelta(days=1)
    date_str = tomorrow.isoformat()

    url = f"https://www.nytimes.com/svc/wordle/v2/{date_str}.json"
    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        solution = data.get("solution")
        if not solution:
            raise ValueError("No solution field in response")
        return jsonify({"date": date_str, "solution": solution.lower()})
    except Exception as e:
        return jsonify({"date": date_str, "error": str(e)}), 502