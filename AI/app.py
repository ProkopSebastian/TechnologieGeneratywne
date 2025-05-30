from flask import Flask, request, jsonify
from rag import ask_rag


app = Flask(__name__)

@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"status": "error", "message": "Missing 'query' in request"}), 400

    result = ask_rag(data["query"])
    return jsonify(result)

if __name__ == "__main__":
    print("Starting Flask server...")
    app.run(host="0.0.0.0", port=5000, debug=True)
