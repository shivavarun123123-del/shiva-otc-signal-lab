
import os
import requests
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

API_URL = "https://otcharts.com/v1"
API_KEY = os.environ.get("OTCHARTS_API_KEY", "")

PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SHIVA OTC SIGNAL LAB</title>
<style>
body {background:#080d18;color:white;font-family:Arial;
text-align:center;padding:20px}
h1 {color:#00e676}
.card {background:#172337;padding:22px;border-radius:15px;
margin:20px auto;max-width:500px}
button,select {padding:13px;margin:8px;border-radius:8px;
font-size:16px}
button {background:#00c875;color:#07120d;border:0}
pre {white-space:pre-wrap;overflow-wrap:anywhere}
</style>
</head>
<body>
<h1>SHIVA OTC SIGNAL LAB</h1>
<div class="card">
<h2>OTC Market Dashboard</h2>
<p>API Connection Test</p>
<select id="symbol">
<option value="EURUSD_otc">EUR/USD OTC</option>
</select>
<br>
<button onclick="loadCandles()">Fetch Candles</button>
<p id="status">Waiting for test...</p>
<pre id="data"></pre>
</div>
<script>
async function loadCandles() {
 const status=document.getElementById("status");
 const data=document.getElementById("data");
 status.textContent="Connecting to OTCharts...";
 data.textContent="";
 try {
  const symbol=document.getElementById("symbol").value;
  const r=await fetch("/api/candles?symbol="+encodeURIComponent(symbol));
  const j=await r.json();
  if(!r.ok) throw new Error(j.error || "API request failed");
  status.textContent="Candles received: "+j.count;
  data.textContent=JSON.stringify(j.candles.slice(-5),null,2);
 } catch(e) {
  status.textContent="Connection error: "+e.message;
 }
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(PAGE)

@app.route("/health")
def health():
    return jsonify({"status": "OK"})

@app.route("/api/venues")
def venues():
    if not API_KEY:
        return jsonify({"error": "API key missing"}), 503
    try:
        r = requests.get(
            API_URL + "/venues",
            headers={"Authorization": "Bearer " + API_KEY},
            timeout=20
        )
        return jsonify(r.json()), r.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502

@app.route("/api/candles")
def candles():
    if not API_KEY:
        return jsonify({"error": "OTCHARTS_API_KEY missing"}), 503

    symbol = request.args.get("symbol", "EURUSD_otc")
    if not symbol.replace("_", "").isalnum():
        return jsonify({"error": "Invalid symbol"}), 400

    try:
        r = requests.get(
            API_URL + "/candles",
            headers={"Authorization": "Bearer " + API_KEY},
            params={
                "venue": "otc",
                "symbol": symbol,
                "tf": 60,
                "limit": 100
            },
            timeout=20
        )
        try:
            result = r.json()
        except ValueError:
            result = {"error": "Invalid response from OTCharts"}

        if r.status_code != 200:
            return jsonify({
                "error": result.get("error", "OTCharts request failed"),
                "upstream_status": r.status_code
            }), 502

        return jsonify(result)

    except requests.RequestException:
        return jsonify({"error": "Could not connect to OTCharts"}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0",
            port=int(os.environ.get("PORT", 10000)))

