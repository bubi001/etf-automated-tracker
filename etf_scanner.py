import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.cluster import AgglomerativeClustering

ETF_TICKERS = [
    "NIFTYBEES.NS", "BANKBEES.NS", "ITBEES.NS", 
    "JUNIORBEES.NS", "MID150BEES.NS", "GOLDBEES.NS", 
    "SILVERBEES.NS", "MON100.NS", "CPSEETF.NS"
]

def get_etf_data(ticker, period="6y"):
    try:
        df = yf.download(ticker, period=period, progress=False, group_by='column')
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(col).strip() for col in df.columns]
        for col in ['Close', 'High', 'Low', 'Volume']:
            if col in df.columns:
                if isinstance(df[col], pd.DataFrame):
                    df[col] = df[col].iloc[:, 0]
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=['Close'])
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def calculate_moving_averages(df):
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['SMA_500'] = df['Close'].rolling(window=500).mean()
    df['SMA_1100'] = df['Close'].rolling(window=1100).mean()
    return df

def detect_crossovers(df):
    if 'SMA_1100' not in df.columns or df['SMA_1100'].isna().all():
        return "Insufficient Data", []
    
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    if float(last_row['SMA_200']) > float(last_row['SMA_500']) > float(last_row['SMA_1100']):
        state = "Full Bullish Stack"
    elif float(last_row['SMA_200']) < float(last_row['SMA_500']) < float(last_row['SMA_1100']):
        state = "Full Bearish Stack"
    else:
        state = "Consolidation/Mixed"
        
    alerts = []
    for ma_fast, ma_slow in [('SMA_200', 'SMA_500'), ('SMA_500', 'SMA_1100'), ('SMA_200', 'SMA_1100')]:
        if float(prev_row[ma_fast]) <= float(prev_row[ma_slow]) and float(last_row[ma_fast]) > float(last_row[ma_slow]):
            alerts.append(f"🚀 {ma_fast} crossed ABOVE {ma_slow}")
        elif float(prev_row[ma_fast]) >= float(prev_row[ma_slow]) and float(last_row[ma_fast]) < float(last_row[ma_slow]):
            alerts.append(f"⚠️ {ma_fast} crossed BELOW {ma_slow}")
            
    return state, alerts

def find_support_resistance(df, clusters=5):
    df['Min'] = df['Low'][(df['Low'] < df['Low'].shift(5)) & (df['Low'] < df['Low'].shift(-5))]
    df['Max'] = df['High'][(df['High'] > df['High'].shift(5)) & (df['High'] > df['High'].shift(-5))]
    pivots = pd.concat([df['Min'].dropna(), df['Max'].dropna()]).values.reshape(-1, 1)
    
    if len(pivots) < clusters: return [], []
    
    clustering = AgglomerativeClustering(n_clusters=clusters, linkage='ward').fit(pivots)
    levels = []
    for i in range(clusters):
        levels.append(np.mean(pivots[clustering.labels_ == i]))
        
    levels.sort()
    current_price = float(df['Close'].iloc[-1])
    supports = [round(float(x), 2) for x in levels if x < current_price]
    resistances = [round(float(x), 2) for x in levels if x > current_price]
    return supports[-2:], resistances[:2]

def detect_delivery_spikes(df, volume_threshold=2.5):
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20']
    ratio = float(df.iloc[-1]['Vol_Ratio'])
    
    if ratio >= volume_threshold:
        return f"🚨 SPIKE: {round(ratio, 2)}x!", True
    return f"Normal ({round(ratio, 2)}x)", False

def send_telegram_alert(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram keys missing from environment secrets.")
        return
    url = f"https://telegram.org{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram dispatch failed: {e}")

if __name__ == "__main__":
    print("🔄 Running Indian ETF History & Alert Pipeline...")
    new_results = []
    notable_events = []
    
    for ticker in ETF_TICKERS:
        df = get_etf_data(ticker)
        if df is None or len(df) < 1100: continue
            
        df = calculate_moving_averages(df)
        ma_status, cross_alerts = detect_crossovers(df)
        supports, resistances = find_support_resistance(df)
        delivery_status, is_spike = detect_delivery_spikes(df)
        current_price = round(float(df['Close'].iloc[-1]), 2)
        
        name = ticker.replace(".NS", "")
        
        # Log any active market trigger event
        if cross_alerts:
            for alert in cross_alerts:
                notable_events.append(f"*{name}*: {alert}")
        if is_spike:
            notable_events.append(f"*{name}*: Large Trade Volume Breakout ({delivery_status})")
            
        new_results.append({
            "Date": pd.Timestamp.now().strftime('%Y-%m-%d'),
            "ETF": ticker,
            "Price": current_price,
            "Closest_Supports": str(supports),
            "Closest_Resistances": str(resistances),
            "Moving_Average_Trend": ma_status,
            "Volume_Alert": delivery_status
        })
        
    new_df = pd.DataFrame(new_results)
    csv_file = "etf_scan_report.csv"
    
    # HISTORY RETENTION MECHANIC: Append if exists, otherwise write fresh
    if os.path.exists(csv_file):
        try:
            old_df = pd.read_csv(csv_file)
            combined_df = pd.concat([old_df, new_df], ignore_index=True)
            # Prevent logging double entries if triggered multiple times the same day
            combined_df.drop_duplicates(subset=['Date', 'ETF'], keep='last', inplace=True)
            combined_df.to_csv(csv_file, index=False)
        except Exception:
            new_df.to_csv(csv_file, index=False)
    else:
        new_df.to_csv(csv_file, index=False)
        
    # TELEGRAM DISPATCH LOGIC
    summary_msg = f"📊 *NSE ETF Scan Summary ({pd.Timestamp.now().strftime('%d-%b-%Y')})*\n\n"
    if notable_events:
        summary_msg += "⚡ *CRITICAL BREAKOUTS TO CHECK:*\n" + "\n".join(notable_events)
    else:
        summary_msg += "✅ No critical crossovers or volume anomalies detected today. Stacking trends are stable."
        
    send_telegram_alert(summary_msg)
    print("✅ Successfully generated history and dispatched Telegram telemetry.")
