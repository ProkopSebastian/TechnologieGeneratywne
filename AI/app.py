from flask import Flask, request, jsonify
# from rag import ask_rag
from mealPlanner import ask_rag
from logger import get_logger

app = Flask(__name__)

@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"status": "error", "message": "Missing 'query' in request"}), 400
    days = data.get("days", 1)
    people = data.get("people", 1)
    query = data["query"]
    result = ask_rag(query, days, people)
    return jsonify(result)

if __name__ == "__main__":
    get_logger("app-main").info("Starting Flask server...")
    app.run(host="0.0.0.0", port=5000, debug=True)
