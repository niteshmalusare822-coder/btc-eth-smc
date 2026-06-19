from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "running"})

if __name__ == "__main__":
    app.run()
