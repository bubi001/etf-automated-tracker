import os
import sys
import yfinance as yf
import pandas as pd
from datetime import datetime

CSV_FILE = "market_price_history.csv"

# Volatility alert parameters
ASSETS = {
    "Gold Spot": {"ticker": "GC=F", "threshold": 1.5},
    "Silver Spot": {"ticker": "SI=F", "threshold": 2.5},
    "Crude Oil Spot": {"ticker": "CL=F", "threshold": 3.0},
    "NASDAQ 100 Index": {"ticker": "^NDX", "threshold": 1.5},
    "Nifty 50 Index": {"ticker": "^NSEI", "threshold": 1.0},
    "HDFC Bank ADR": {"ticker": "HDB", "threshold": 1.5},
    "Infosys ADR": {"ticker": "INFY", "threshold": 2.0},
    "Wipro ADR": {"ticker": "WIT", "threshold": 2.0},
    "ICICI Bank ADR": {"ticker": "IBN", "threshold": 1.5},
    "Dr. Reddy ADR": {"ticker": "RDY", "threshold": 1.5},
    "Reliance Industries GDR": {"ticker": "RIGD.IL", "threshold": 1.5}
}

def monitor_markets():
    # Split timestamp components into distinct fields optimized for Excel filtering/pivots
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    
    new_rows = []
    alert_triggered = False
    alert_summary = []
    
    # Load historical file for anti-duplication processing
    last_stored_prices = {}
    if os.path.exists(CSV_FILE):
        try:
            old_df = pd.read_csv(CSV_FILE)
            if not old_df.empty:
                for asset_name in ASSETS.keys():
                    asset_df = old_df[old_df["Asset"] == asset_name]
                    if not asset_df.empty:
                        last_stored_prices[asset_name] = asset_df.iloc[-1]["Price"]
        except Exception as e:
            print(f"⚠️ History load bypass: {e}")

    print("🔄 Pulling live metrics optimized for Excel spreadsheet ingestion...")
    
    for name, config in ASSETS.items():
        try:
            ticker = yf.Ticker(config["ticker"])
            data = ticker.history(period="2d", interval="1m")
            if data.empty: 
                data = ticker.history(period="5d")
            if len(data) < 2: 
                continue
            
            current_price = round(data['Close'].iloc[-1], 2)
            previous_close = round(data['Close'].iloc[-2], 2)
            percent_change = round(((current_price - previous_close) / previous_close) * 100, 2)
            
            # --- ANTI-DUPLICATION ENGINE ---
            if name in last_stored_prices and last_stored_prices[name] == current_price:
                print(f"箱️ Skipping {name}: Price flat at {current_price}. Excel rows protected.")
                continue
            
            # Append pure data points (No mixed strings or prefix currency marks to keep Excel formulas working)
            new_rows.append({
                "Date": current_date,
                "Time": current_time,
                "Asset": name,
                "Ticker": config["ticker"],
                "Price": current_price,
                "Change_Percent": percent_change
            })
            
            print(f"🔹 {name}: {current_price} | {percent_change:+.2f}%")
            
            if abs(percent_change) >= config["threshold"]:
                alert_triggered = True
                emoji = "🚨" if percent_change < 0 else "🚀"
                alert_summary.append(f"{emoji} {name}: {current_price} ({percent_change:+.2f}%)")
                
        except Exception as e:
            print(f"❌ Processing block on {name}: {e}")
            
    # Commit table dataset array to historical file
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        if os.path.exists(CSV_FILE):
            try:
                old_df = pd.read_csv(CSV_FILE)
                combined_df = pd.concat([old_df, new_df], ignore_index=True).tail(2000)
            except:
                combined_df = new_df
        else:
            combined_df = new_df
        combined_df.to_csv(CSV_FILE, index=False)
        print("✅ Structured layout committed to market_price_history.csv.")
    else:
        print("⏸️ Zero price changes detected. File preservation state locked.")

    if alert_triggered:
        error_msg = " | ".join(alert_summary)
        sys.exit(f"Market Alert: {error_msg}")

if __name__ == "__main__":
    monitor_markets()
