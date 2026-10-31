import os
import requests
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
API_URL = "https://api.twelvedata.com/time_series"

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SHIVA OTC SIGNAL LAB</title>
<style>
body { background:#101820; color:white; font-family:Arial; padding:20px; }
.card { background:#1d2b38; padding:18px; border-radius:12px; margin-top:15px; }
h1 { color:#00e6a0; }
button,select { padding:12px; border-radius:7px; margin:5px; }
button { background:#00c98b; border:0; font-weight:bold; }
table { width:100%; margin-top:15px; border-collapse:collapse; }
td,th { padding:8px; border-bottom:1px solid #52606d; text-align:center; }
#result { overflow-x:auto; }
</style>
</head>
<body>
<h1>SHIVA OTC SIGNAL LAB</h1>
<div class="card">
<h3>Trading Dashboard</h3>
<p>Bot Status: Connected</p>
<p>Data Source: Twelve Data</p>
<select id="symbol">
<option value="EUR/USD">EUR/USD</option>
<option value="GBP/USD">GBP/USD</option>
<option value="USD/JPY">USD/JPY</option>
</select>
<button onclick="fetchCandles()">Fetch Candles</button>
<div id="result">Candles yahan dikhengi.</div>
</div>
<script>
async function fetchCandles() {
 const symbol = document.getElementById("symbol").value;
 const result = document.getElementById("result");
 result.innerHTML = "Loading...";
 try {
  const response = await fetch("/api/candles?symbol=" + encodeURIComponent(symbol));
  const data = await response.json();
  if (!response.ok) {
    result.innerHTML = "Error: " + (data.error || "Data nahi mila");
    return;
  }
  let html = "<p>Total candles: " + data.count + "</p>";
  html += "<table><tr><th>Time</th><th>Open</th><th>High</th><th>Low</th><th>Close</th></tr>";
  data.candles.forEach(c => {
    html += "<tr><td>"+c.datetime+"</td><td>"+c.open+"</td><td>"+c.high+"</td><td>"+c.low+"</td><td>"+c.close+"</td></tr>";
  });
  html += "</table>";
  result.innerHTML = html;
 } catch(e) {
  result.innerHTML = "Connection error: " + e.message;
 }
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/candles")
def candles():
    if not API_KEY:
        return jsonify({"error": "TWELVE_DATA_API_KEY Render Environment mein missing hai"}), 500

    symbol = request.args.get("symbol", "EUR/USD")
    allowed = ["EUR/USD", "GBP/USD", "USD/JPY"]

    if symbol not in allowed:
        return jsonify({"error": "Invalid symbol"}), 400

    try:
        response = requests.get(
            API_URL,
            params={
                "symbol": symbol,
                "interval": "1min",
                "outputsize": 30,
                "apikey": API_KEY
            },
            timeout=20
        )

        data = response.json()

        if response.status_code != 200 or "values" not in data:
            message = data.get("message", data.get("code", "Data unavailable"))
            return jsonify({"error": str(message)}), 502

        return jsonify({
            "symbol": symbol,
            "count": len(data["values"]),
            "candles": data["values"]
        })

    except requests.exceptions.RequestException:
        return jsonify({"error": "Twelve Data se connect nahi ho pa raha"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

