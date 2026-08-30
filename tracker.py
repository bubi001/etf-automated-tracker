import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

CSV_FILE = "market_price_history.csv"
ASSETS = {
    "Gold": {"ticker": "GC=F", "threshold": 1.5},
    "Silver": {"ticker": "SI=F", "threshold": 2.5},
    "Crude Oil": {"ticker": "CL=F", "threshold": 3.0},
    "NASDAQ 100": {"ticker": "^NDX", "threshold": 1.5},
    "GIFT Nifty": {"ticker": "^NSEIX", "threshold": 1.0}
}

def send_alert(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        url = f"https://telegram.org{bot_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"Alert failed: {e}")

def monitor_markets():
    alert_messages = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_rows = []
    
    for name, config in ASSETS.items():
        try:
            ticker = yf.Ticker(config["ticker"])
            data = ticker.history(period="2d", interval="1m")
            if data.empty: data = ticker.history(period="5d")
            if len(data) < 2: continue
            
            current_price = data['Close'].iloc[-1]
            previous_close = data['Close'].iloc[-2]
            percent_change = ((current_price - previous_close) / previous_close) * 100
            
            # Stage records for file writing
            new_rows.append({
                "Timestamp": current_time,
                "Asset": name,
                "Ticker": config["ticker"],
                "Price": round(current_price, 2),
                "Change_Percent": round(percent_change, 2)
            })
            
            if abs(percent_change) >= config["threshold"]:
                emoji = "🚨" if percent_change < 0 else "🚀"
                alert_messages.append(f"{emoji} *{name} Big Shift!*\\n• Price: `{current_price:.2f}`\\n• Change: `{percent_change:+.2f}%`\\n")
        except Exception as e:
            print(f"Extraction block on {name}: {e}")
            
    # Compile and append files in-memory
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        if os.path.exists(CSV_FILE):
            try:
                old_df = pd.read_csv(CSV_FILE)
                combined_df = pd.concat([old_df, new_df], ignore_index=True).tail(1000)
            except:
                combined_df = new_df
        else:
            combined_df = new_df
        combined_df.to_csv(CSV_FILE, index=False)
        print("✅ market_price_history.csv file successfully populated.")
        
    if alert_messages:
        send_alert("\n".join(alert_messages))

if __name__ == "__main__":
    monitor_markets()
