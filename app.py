
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <html>
    <head>
        <title>SHIVA OTC SIGNAL LAB</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                background: #080d18;
                color: white;
                font-family: Arial;
                text-align: center;
                padding: 40px 15px;
            }
            h1 { color: #00e676; }
            .card {
                background: #172337;
                padding: 25px;
                border-radius: 15px;
                margin-top: 30px;
            }
        </style>
    </head>
    <body>
        <h1>SHIVA OTC SIGNAL LAB</h1>
        <div class="card">
            <h2>Trading Dashboard</h2>
            <p>Bot Status: Connected</p>
            <p>Signal Engine: Ready</p>
            <p>Welcome to Shiva OTC Lab</p>
        </div>
    </body>
    </html>
    """

@app.route("/health")
def health():
    return jsonify({"status": "OK"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
