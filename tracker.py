import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

CSV_FILE = "market_price_history.csv"

# Reconfigured exclusively for raw spot/index feeds and structural ADR tickers
ASSETS = {
    # --- Underlying Raw Spot & Index Benchmarks ---
    "Gold Spot": {"ticker": "GC=F", "threshold": 1.5},
    "Silver Spot": {"ticker": "SI=F", "threshold": 2.5},
    "Crude Oil Spot": {"ticker": "CL=F", "threshold": 3.0},
    "NASDAQ 100 Index": {"ticker": "^NDX", "threshold": 1.5},
    "Nifty 50 Index": {"ticker": "^NSEI", "threshold": 1.0},
    
    # --- High-Volume Institutional ADRs & Equities ---
    "HDFC Bank ADR": {"ticker": "HDB", "threshold": 1.5},
    "Infosys ADR": {"ticker": "INFY", "threshold": 2.0},
    "Wipro ADR": {"ticker": "WIT", "threshold": 2.0},
    "ICICI Bank ADR": {"ticker": "IBN", "threshold": 1.5},
    "Dr. Reddy ADR": {"ticker": "RDY", "threshold": 1.5},
    "Reliance Industries": {"ticker": "RELIANCE.NS", "threshold": 1.5}
}

def send_alert(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        url = f"https://telegram.org{bot_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"Alert dispatch exception: {e}")

def monitor_markets():
    alert_messages = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_rows = []
    
    print("🔄 Pulling live metrics from exact Spot Prices & ADR channels...")
    
    for name, config in ASSETS.items():
        try:
            ticker = yf.Ticker(config["ticker"])
            # Pull intraday updates for high-precision volatility testing
            data = ticker.history(period="2d", interval="1m")
            if data.empty: 
                data = ticker.history(period="5d")
            if len(data) < 2: 
                continue
            
            current_price = data['Close'].iloc[-1]
            previous_close = data['Close'].iloc[-2]
            percent_change = ((current_price - previous_close) / previous_close) * 100
            
            # Map clean contextual regional currency headers
            if config["ticker"].endswith(".NS"):
                currency = "₹"
            elif config["ticker"].startswith("^"):
                currency = " pts" # Represent base index units cleanly
            else:
                currency = "$"
            
            # Stage historical matrix record
            new_rows.append({
                "Timestamp": current_time,
                "Asset": name,
                "Ticker": config["ticker"],
                "Price": round(current_price, 2),
                "Change_Percent": round(percent_change, 2)
            })
            
            # Print status to GitHub Action run consoles
            price_display = f"{current_price:.2f}{currency}" if currency == " pts" else f"{currency}{current_price:.2f}"
            print(f"🔹 {name}: {price_display} | {percent_change:+.2f}%")
            
            # Check threshold logic
            if abs(percent_change) >= config["threshold"]:
                emoji = "🚨" if percent_change < 0 else "🚀"
                alert_messages.append(
                    f"{emoji} *{name} Volatility Alert!*\n"
                    f"• Current Price: `{price_display}`\n"
                    f"• Intraday Change: `{percent_change:+.2f}%` (Threshold: {config['threshold']}%)\n"
                )
        except Exception as e:
            print(f"❌ Extraction pipeline block on asset {name}: {e}")
            
    # Append structured dataset update to local CSV history file
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        if os.path.exists(CSV_FILE):
            try:
                old_df = pd.read_csv(CSV_FILE)
                combined_df = pd.concat([old_df, new_df], ignore_index=True).tail(1500)
            except:
                combined_df = new_df
        else:
            combined_df = new_df
        combined_df.to_csv(CSV_FILE, index=False)
        print("✅ Live metrics committed to market_price_history.csv.")
        
    if alert_messages:
        send_alert("\n".join(alert_messages))
    else:
        print("✅ Markets analyzed. No assets broke historical threshold tolerances.")

if __name__ == "__main__":
    monitor_markets()
