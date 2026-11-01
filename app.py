
import os
import requests
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "").strip()

API_URL = "https://api.twelvedata.com/time_series"

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SHIVA OTC SIGNAL LAB</title>
<style>
body{background:#101820;color:white;font-family:Arial;padding:15px}
h1{color:#00e6a0}
.card{background:#1d2b38;padding:16px;border-radius:12px;margin:14px 0}
.signal{font-size:25px;font-weight:bold}
.buy{color:#00e6a0}.sell{color:#ff6464}.wait{color:#ffd166}
small{color:#b8c4ce}
button{background:#00c98b;padding:12px;border:0;border-radius:8px;font-weight:bold}
</style>
</head>
<body>
<h1>SHIVA OTC SIGNAL LAB</h1>
<p>Bot Status: Connected</p>
<p>Data: Twelve Data - Forex</p>

<div class="card">
<h3>Trading Pair</h3>
<select id="symbol">
<option value="EUR/USD">EUR/USD</option>
<option value="GBP/USD">GBP/USD</option>
<option value="USD/JPY">USD/JPY</option>
</select>
<button onclick="loadSignals()">Refresh Signals</button>
</div>

<div id="one" class="card">1M Signal: Loading...</div>
<div id="five" class="card">5M Signal: Loading...</div>
<p><small id="updated">Waiting for data...</small></p>

<script>
function panel(id,title,s){
 let cls=s.signal==="BUY"?"buy":s.signal==="SELL"?"sell":"wait";
 document.getElementById(id).innerHTML=
 `<h2>${title} Signal</h2>
 <div class="signal ${cls}">${s.signal}</div>
 <p>Entry Price: ${s.entry}</p>
 <p>RSI 14: ${s.rsi}</p>
 <p>EMA 9: ${s.ema9}</p>
 <p>EMA 21: ${s.ema21}</p>
 <p>Signal Strength: ${s.strength}</p>
 <small>${s.note}</small>`;
}
async function loadSignals(){
 document.getElementById("one").innerHTML="1M: Loading...";
 document.getElementById("five").innerHTML="5M: Loading...";
 try{
  let symbol=document.getElementById("symbol").value;
  let r=await fetch("/api/signals?symbol="+encodeURIComponent(symbol));
  let text = await r.text();
let d;

try {
    d = JSON.parse(text);
} catch (err) {
    throw new Error("Backend JSON error");
}

if (!r.ok) {
    throw new Error(d.error || "API Error");
}
  if(!r.ok) throw new Error(d.error||"Data error");
  panel("one","1M",d.one);
  panel("five","5M",d.five);
  document.getElementById("updated").innerText=
   "Last update: "+new Date().toLocaleTimeString();
 }catch(e){
  document.getElementById("one").innerText="Error: "+e.message;
  document.getElementById("five").innerText="Please try again later.";
 }
}
loadSignals();
// Free API credits bachane ke liye automatic refresh har 3 minute.
setInterval(loadSignals,180000);
</script>
</body>
</html>
"""

def ema(values, period):
    if len(values) < period:
        return None
    result = sum(values[:period]) / period
    multiplier = 2 / (period + 1)
    for price in values[period:]:
        result = (price - result) * multiplier + result
    return result

def rsi(values, period=14):
    if len(values) <= period:
        return None
    changes = [values[i] - values[i-1] for i in range(1, len(values))]
    gains = [max(x, 0) for x in changes]
    losses = [max(-x, 0) for x in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period-1) + gains[i]) / period
        avg_loss = (avg_loss * (period-1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))

def make_signal(candles):
    if len(candles) < 25:
        raise ValueError("Not enough candles for indicators")

    closes = [float(c["close"]) for c in candles]
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    rv = rsi(closes, 14)
    price = closes[-1]

    signal = "WAIT"
    strength = "Low"
    note = "Clear trend nahi hai. Trade ka wait karein."

    if e9 > e21 and 50 < rv < 70:
        signal = "BUY"
        strength = "Medium"
        note = "EMA bullish aur RSI supportive hai."
    elif e9 < e21 and 30 < rv < 50:
        signal = "SELL"
        strength = "Medium"
        note = "EMA bearish aur RSI supportive hai."
    elif e9 > e21 and rv >= 70:
        note = "RSI overbought zone mein hai. BUY chase na karein."
    elif e9 < e21 and rv <= 30:
        note = "RSI oversold zone mein hai. SELL chase na karein."

    return {
        "signal": signal,
        "entry": round(price, 5),
        "rsi": round(rv, 2),
        "ema9": round(e9, 5),
        "ema21": round(e21, 5),
        "strength": strength,
        "note": note
    }

def aggregate_five_minutes(candles):
    groups = {}
    for c in candles:
        dt = datetime.strptime(c["datetime"], "%Y-%m-%d %H:%M:%S")
        bucket = dt.replace(minute=(dt.minute // 5) * 5, second=0)
        key = bucket.strftime("%Y-%m-%d %H:%M:%S")
        groups.setdefault(key, []).append(c)

    result = []
    for key in sorted(groups):
        group = groups[key]
        result.append({
            "datetime": key,
            "open": group[0]["open"],
            "high": max(float(x["high"]) for x in group),
            "low": min(float(x["low"]) for x in group),
            "close": group[-1]["close"]
        })
    return result

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/signals")
def signals():
    if not API_KEY:
        return jsonify({"error": "TWELVE_DATA_API_KEY missing"}), 500

    symbol = request.args.get("symbol", "EUR/USD")
    if symbol not in ["EUR/USD", "GBP/USD", "USD/JPY"]:
        return jsonify({"error": "Invalid symbol"}), 400

    try:
        response = requests.get(
            API_URL,
            params={
                "symbol": symbol,
                "interval": "1min",
                "outputsize": 250,
                "apikey": API_KEY
            },
            timeout=20
        )
        try:
    data = response.json()
except ValueError:
    return jsonify({"error": "Invalid API response"}), 502

if response.status_code != 200 or "values" not in data:
    return jsonify({
        "error": data.get("message", "Twelve Data error")
    }), 502

if not isinstance(data["values"], list) or not data["values"]:
    return jsonify({"error": "No candle data received"}), 502

        candles = [
    c for c in reversed(data["values"])
    if all(k in c and c[k] is not None
           for k in ["datetime", "open", "high", "low", "close"])
]

if len(candles) < 25:
    return jsonify({"error": "Not enough valid candles"}), 502
        five_candles = aggregate_five_minutes(candles)

        return jsonify({
            "symbol": symbol,
            "one": make_signal(candles),
            "five": make_signal(five_candles)
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 502
    except requests.exceptions.RequestException:
        return jsonify({"error": "Could not connect to Twelve Data"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


