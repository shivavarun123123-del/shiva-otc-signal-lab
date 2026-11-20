
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
<title>SHIVA OTC SIGNAL LAB V2.3</title>

<style>
body {
    background:#101820;
    color:white;
    font-family:Arial;
    padding:15px;
}
h1 {color:#00e6a0}
.card {
    background:#1d2b38;
    padding:16px;
    border-radius:12px;
    margin:14px 0;
}
.signal {
    font-size:27px;
    font-weight:bold;
}
.buy {color:#00e6a0}
.sell {color:#ff6464}
.wait {color:#ffd166}
small {color:#b8c4ce}
button {
    background:#00c98b;
    padding:10px;
    border:0;
    border-radius:8px;
    font-weight:bold;
    margin:4px;
}
select {
    padding:10px;
    border-radius:7px;
}
.win {color:#00e6a0}
.loss {color:#ff6464}
.history-item {
    background:#263746;
    padding:12px;
    border-radius:9px;
    margin:10px 0;
}
.stats {
    font-size:23px;
    font-weight:bold;
    color:#00e6a0;
}
</style>
</head>

<body>

<h1>SHIVA OTC SIGNAL LAB</h1>
<p>Bot Status: Connected</p>
<p>Engine: Smart Confirmation V2.3</p>

<div class="card">
<h3>Trading Pair</h3>
<select id="symbol">
<option value="EUR/USD">EUR/USD</option>
<option value="GBP/USD">GBP/USD</option>
<option value="USD/JPY">USD/JPY</option>
</select>
<button onclick="loadSignals()">Refresh Signals</button>
</div>

<div id="final" class="card">
<h2>FINAL CONFIRMATION V2.3</h2>
<div class="signal wait">WAIT</div>
<p>Waiting for analysis...</p>
</div>

<div id="early" class="card">
    <h2>EARLY TREND DETECTION V2.4.1</h2>
    <div id="earlySignal">NO SETUP</div>
    <p id="earlyNote">Waiting for momentum analysis...</p>
</div>

<div id="one" class="card">1M Signal: Loading...</div>
<div id="five" class="card">5M Signal: Loading...</div>

<div class="card">
<h2>ACCURACY TRACKER</h2>
<p>Wins: <span id="wins">0</span></p>
<p>Losses: <span id="losses">0</span></p>
<p>Resolved Trades: <span id="resolved">0</span></p>
<div class="stats" id="accuracy">0%</div>
<small>Accuracy is based only on manually marked outcomes.</small>
</div>

<div class="card">
<h2>SIGNAL HISTORY</h2>
<p><small>Last 10 signals</small></p>
<div id="history">No signals recorded yet.</div>
<button onclick="clearHistory()">Clear History</button>
</div>

<p><small id="updated">Waiting for data...</small></p>

<script>


let verificationBusy = false;

const HISTORY_KEY = "shiva_otc_v23_history";

function getHistory() {
    try {
        return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
    } catch(e) {
        return [];
    }
}

function saveHistory(history) {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&":"&amp;",
        "<":"&lt;",
        ">":"&gt;",
        '"':"&quot;",
        "'":"&#39;"
    })[c]);
}

function panel(id, title, s) {
    let cls = s.signal === "BUY" ? "buy" :
              s.signal === "SELL" ? "sell" : "wait";

    document.getElementById(id).innerHTML = `
    <h2>${title} Signal</h2>
    <div class="signal ${cls}">${escapeHTML(s.signal)}</div>
    <p>Entry Price: ${escapeHTML(s.entry)}</p>
    <p>Candle Momentum: ${escapeHTML(s.momentum)}</p>
    <p>RSI 14: ${escapeHTML(s.rsi)}</p>
    <p>EMA 9: ${escapeHTML(s.ema9)}</p>
    <p>EMA 21: ${escapeHTML(s.ema21)}</p>
    <p>Signal Strength: ${escapeHTML(s.strength)}</p>
    <small>${escapeHTML(s.note)}</small>`;
}

function finalPanel(s) {
    let cls = s.signal === "BUY" ? "buy" :
              s.signal === "SELL" ? "sell" : "wait";

    document.getElementById("final").innerHTML = `
    <h2>FINAL CONFIRMATION V2.4</h2>
    <div class="signal ${cls}">${escapeHTML(s.signal)}</div>
    <p>Entry Price: ${escapeHTML(s.entry)}</p>
    <p>Confirmation Score: ${escapeHTML(s.score)}/100</p>
    <p>Candle Momentum: ${escapeHTML(s.momentum)}</p>
    <p>Confirmation: ${escapeHTML(s.confirmation)}</p>
    <p>Signal Strength: ${escapeHTML(s.strength)}</p>
    <small>${escapeHTML(s.note)}</small>`;
}

// SAVE NEW SIGNAL
function recordSignal(symbol, s) {
    let history = getHistory();
    let now = Date.now();

    let entry = String(s.entry);
    let last = history[0];

    if (last &&
        last.symbol === symbol &&
        last.signal === s.signal &&
        last.entry === entry &&
        now - last.time < 180000) {
        return;
    }

    let tradable = s.signal === "BUY" || s.signal === "SELL";

    history.unshift({
        symbol: symbol,
        signal: s.signal,
        entry: entry,
        score: s.score,
        strength: s.strength,
        note: s.note,
        time: now,
        verifyAt: tradable ? now + 60000 : null,
        outcome: null,
        exitPrice: null
    });

    history = history.slice(0, 10);

    saveHistory(history);
    renderHistory();
}

// AUTOMATIC 1 MINUTE VERIFICATION
async function checkPendingSignals() {
    if (verificationBusy) return;

    let history = getHistory();
    let now = Date.now();

    let index = history.findIndex(x =>
        (x.signal === "BUY" || x.signal === "SELL") &&
        !x.outcome &&
        x.verifyAt &&
        now >= x.verifyAt
    );

    if (index === -1) return;

    verificationBusy = true;

    try {
        let item = history[index];

        let response = await fetch(
            "/api/signals?symbol=" +
            encodeURIComponent(item.symbol)
        );

        let data = await response.json();

        if (!response.ok || !data.one) {
            throw new Error(data.error || "Price verification failed");
        }

        let entry = Number(item.entry);
        let exit = Number(data.one.entry);

        if (!Number.isFinite(entry) ||
            !Number.isFinite(exit)) {
            throw new Error("Invalid verification price");
        }

        let outcome = "DRAW";

        if (exit > entry) {
            outcome = item.signal === "BUY" ? "WIN" : "LOSS";
        } else if (exit < entry) {
            outcome = item.signal === "SELL" ? "WIN" : "LOSS";
        }

        history = getHistory();

        let current = history.find(x => x.time === item.time);

        if (!current || current.outcome) return;

        current.outcome = outcome;
        current.exitPrice = exit;
        current.verifiedAt = Date.now();

        saveHistory(history);
        renderHistory();

    } catch(e) {
        console.warn("Auto verification:", e.message);
    } finally {
        verificationBusy = false;
    }
}

// HISTORY AND ACCURACY
function renderHistory() {
    let history = getHistory();

    let wins = history.filter(x => x.outcome === "WIN").length;
    let losses = history.filter(x => x.outcome === "LOSS").length;
    let draws = history.filter(x => x.outcome === "DRAW").length;

    let resolved = wins + losses + draws;
    let decided = wins + losses;

    let accuracy = decided > 0
        ? ((wins / decided) * 100).toFixed(1)
        : "0.0";

    document.getElementById("wins").innerText = wins;
    document.getElementById("losses").innerText = losses;
    document.getElementById("resolved").innerText = resolved;
    document.getElementById("accuracy").innerText = accuracy + "%";

    if (history.length === 0) {
        document.getElementById("history").innerHTML =
            "No signals recorded yet.";
        return;
    }

    document.getElementById("history").innerHTML =
        history.map(x => {
            let cls = x.signal === "BUY" ? "buy" :
                      x.signal === "SELL" ? "sell" : "wait";

            let result = x.outcome === "WIN"
                ? '<span class="win">AUTO WIN</span>'
                : x.outcome === "LOSS"
                ? '<span class="loss">AUTO LOSS</span>'
                : x.outcome === "DRAW"
                ? '<span>DRAW</span>'
                : x.signal === "WAIT"
                ? '<span>NO TRADE</span>'
                : x.verifyAt
                ? '<span>WAITING FOR 1M VERIFICATION</span>'
                : '<span>OLD RECORD - NOT VERIFIED</span>';

            return `
            <div class="history-item">
                <b>${escapeHTML(x.symbol)}</b>
                <div class="signal ${cls}">
                    ${escapeHTML(x.signal)}
                </div>
                <p>Entry: ${escapeHTML(x.entry)}</p>
                <p>Exit: ${x.exitPrice === null ? "Pending" : escapeHTML(x.exitPrice)}</p>
                <p>Score: ${escapeHTML(x.score)}/100</p>
                <p>Strength: ${escapeHTML(x.strength)}</p>
                <p>Time: ${new Date(x.time).toLocaleString()}</p>
                <p>Result: ${result}</p>
            </div>`;
        }).join("");
}

// CLEAR HISTORY
function clearHistory() {
    if (!confirm("Delete all signal history?")) return;

    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
}

// LOAD LIVE SIGNALS
async function loadSignals() {
    document.getElementById("one").innerText = "1M: Loading...";
    document.getElementById("five").innerText = "5M: Loading...";
    document.getElementById("final").innerText = "Analyzing...";

    try {
        let symbol = document.getElementById("symbol").value;

        let response = await fetch(
            "/api/signals?symbol=" + encodeURIComponent(symbol)
        );

        let data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "API Error");
        }

        panel("one", "1M", data.one);
        panel("five", "5M", data.five);
        finalPanel(data.final);
        
const early = data.final.early_signal || "NONE";

document.getElementById("earlySignal").innerText =
    early === "NONE" ? "NO SETUP" : early;

document.getElementById("earlyNote").innerText =
    early === "NONE"
        ? "Waiting for both timeframes to confirm momentum."
        : early + " detected. Final confirmation ka wait karein.";


        recordSignal(symbol, data.final);

        document.getElementById("updated").innerText =
            "Last update: " + new Date().toLocaleTimeString();

    } catch(e) {
        document.getElementById("one").innerText =
            "Error: " + e.message;

        document.getElementById("five").innerText =
            "Please try again later.";

        document.getElementById("final").innerText =
            "Confirmation unavailable.";
    }
}

renderHistory();
loadSignals();

setInterval(loadSignals, 180000);
setInterval(checkPendingSignals, 5000);

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

    changes = [
        values[i] - values[i-1]
        for i in range(1, len(values))
    ]

    gains = [max(x, 0) for x in changes]
    losses = [max(-x, 0) for x in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (
            avg_gain * (period - 1) + gains[i]
        ) / period

        avg_loss = (
            avg_loss * (period - 1) + losses[i]
        ) / period

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
    last_candle = candles[-1]

    if float(last_candle["close"]) > float(last_candle["open"]):
        momentum = "BULLISH"
    elif float(last_candle["close"]) < float(last_candle["open"]):
        momentum = "BEARISH"
    else:
        momentum = "NEUTRAL"

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
        note = "RSI overbought hai. BUY chase na karein."

    elif e9 < e21 and rv <= 30:
        note = "RSI oversold hai. SELL chase na karein."

    return { 
        "momentum": momentum,
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
        dt = datetime.strptime(
            c["datetime"], "%Y-%m-%d %H:%M:%S"
        )

        bucket = dt.replace(
            minute=(dt.minute // 5) * 5,
            second=0
        )

        key = bucket.strftime("%Y-%m-%d %H:%M:%S")
        groups.setdefault(key, []).append(c)

    result = []

    for key in sorted(groups):
        group = sorted(
            groups[key],
            key=lambda x: x["datetime"]
        )

        if len(group) != 5:
            continue

        times = [
            datetime.strptime(
                c["datetime"], "%Y-%m-%d %H:%M:%S"
            )
            for c in group
        ]

        if [t.minute % 5 for t in times] != [0, 1, 2, 3, 4]:
            continue

        result.append({
            "datetime": key,
            "open": float(group[0]["open"]),
            "high": max(float(x["high"]) for x in group),
            "low": min(float(x["low"]) for x in group),
            "close": float(group[-1]["close"])
        })

    return result




    

def smart_confirmation(one, five):
    signal1 = one["signal"]
    signal5 = five["signal"]

    momentum1 = one["momentum"]
    momentum5 = five["momentum"]

    score = 0
    signal = "WAIT"
    early_signal = "NONE"
    confirmation = "Timeframe mismatch"
    note = "Clear confirmation nahi hai."

    # EARLY TREND DETECTION
    if momentum1 == "BULLISH" and momentum5 == "BULLISH":
        early_signal = "EARLY BUY"

    elif momentum1 == "BEARISH" and momentum5 == "BEARISH":
        early_signal = "EARLY SELL"

    # BUY CONFIRMATION
    if signal1 == "BUY" and signal5 == "BUY":
        confirmation = "1M + 5M BUY Agreement"
        score += 30

        if one["ema9"] > one["ema21"] and five["ema9"] > five["ema21"]:
            score += 25

        if 50 < one["rsi"] < 70 and 50 < five["rsi"] < 70:
            score += 15

        if momentum1 == "BULLISH" and momentum5 == "BULLISH":
            score += 30
            signal = "BUY"
            note = "Bullish trend fully confirmed."

    # SELL CONFIRMATION
    elif signal1 == "SELL" and signal5 == "SELL":
        confirmation = "1M + 5M SELL Agreement"
        score += 30

        if one["ema9"] < one["ema21"] and five["ema9"] < five["ema21"]:
            score += 25

        if 30 < one["rsi"] < 50 and 30 < five["rsi"] < 50:
            score += 15

        if momentum1 == "BEARISH" and momentum5 == "BEARISH":
            score += 30
            signal = "SELL"
            note = "Bearish trend fully confirmed."

    else:
        note = "Timeframe signals match nahi kar rahe."

    score = max(0, min(score, 100))

    if signal == "WAIT":
        strength = "Weak"
        if early_signal != "NONE":
            confirmation = "Early momentum detected"
            note = early_signal + " detected. Final confirmation ka wait karein."
    elif score >= 85:
        strength = "Strong"
    elif score >= 70:
        strength = "Medium"
    else:
        signal = "WAIT"
        strength = "Weak"
        note = "Confirmation score kam hai."

    return {
        "signal": signal,
        "early_signal": early_signal,
        "entry": one["entry"],
        "strength": strength,
        "score": score,
        "confirmation": confirmation,
        "momentum": momentum1 + " / " + momentum5,
        "note": note
    }

       
        
@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "V2.2"})


@app.route("/api/signals")
def signals():
    if not API_KEY:
        return jsonify({
            "error": "TWELVE_DATA_API_KEY missing"
        }), 500

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
            return jsonify({
                "error": "Invalid API response"
            }), 502

        if response.status_code != 200 or "values" not in data:
            return jsonify({
                "error": data.get(
                    "message", "Twelve Data error"
                )
            }), 502

        if not isinstance(data["values"], list) or not data["values"]:
            return jsonify({
                "error": "No candle data received"
            }), 502

        candles = [
            c for c in reversed(data["values"])
            if all(
                k in c and c[k] is not None
                for k in [
                    "datetime", "open", "high",
                    "low", "close"
                ]
            )
        ]

        if len(candles) < 25:
            return jsonify({
                "error": "Not enough valid candles"
            }), 502

        five_candles = aggregate_five_minutes(candles)

        if len(five_candles) < 25:
            return jsonify({
                "error": "Not enough complete 5M candles"
            }), 502

        one = make_signal(candles)
        five = make_signal(five_candles)
        final = smart_confirmation(one, five)

        return jsonify({
            "symbol": symbol,
            "one": one,
            "five": five,
            "final": final
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 502

    except requests.exceptions.RequestException:
        return jsonify({
            "error": "Could not connect to Twelve Data"
        }), 502

    except Exception as e:
        app.logger.exception("Signal engine error")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )

