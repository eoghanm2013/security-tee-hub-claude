from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/")
def health():
    return jsonify(status="ok", tracer="python")

@app.route("/search")
def search():
    q = request.args.get("q", "")
    return jsonify(query=q, results=[f"result-{i}" for i in range(5)])

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    return jsonify(authenticated=False, user=username)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
