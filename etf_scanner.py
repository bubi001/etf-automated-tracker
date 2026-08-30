import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.cluster import AgglomerativeClustering

# --- CONFIGURATION ---
# List out any liquid ETFs you want tracked here
 # --- CONFIGURATION (INDIAN NSE ETFS) ---
# .NS suffix is required for yfinance to fetch data from the National Stock Exchange of India
ETF_TICKERS = [
    "NIFTYBEES.NS",   # Nippon India Nifty 50 ETF (Core Index)
    "BANKBEES.NS",    # Nippon India Nifty Bank ETF (Banking Sector)
    "ITBEES.NS",      # Nippon India Nifty IT ETF (Tech Sector)
    "JUNIORBEES.NS",  # Nippon India Nifty Next 50 ETF (Next 50 Large Caps)
    "MID150BEES.NS",  # Nippon India Nifty Midcap 150 ETF (Mid Caps)
    "GOLDBEES.NS",    # Nippon India Gold ETF (Gold Commodities)
    "SILVERBEES.NS",  # Nippon India Silver ETF (Silver Commodities)
    "MON100.NS",      # Motilal Oswal Nasdaq 100 ETF (US Tech Exposure)
    "CPSEETF.NS"      # Nippon India CPSE ETF (Public Sector Undertakings)
]

def get_etf_data(ticker, period="6y"):
    try:
        df = yf.download(ticker, period=period, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def calculate_moving_averages(df):
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['SMA_500'] = df['Close'].rolling(window=500).mean()
    df['SMA_1100'] = df['Close'].rolling(window=1100).mean()
    return df

def detect_crossovers(df):
    if df['SMA_1100'].isna().all():
        return "Insufficient Data (Needs ~4.5 years)"
    
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    # Identify basic structural stacking state
    if last_row['SMA_200'] > last_row['SMA_500'] > last_row['SMA_1100']:
        state = "Full Bullish Stack"
    elif last_row['SMA_200'] < last_row['SMA_500'] < last_row['SMA_1100']:
        state = "Full Bearish Stack"
    else:
        state = "Consolidation/Mixed"
        
    # Check for exact trigger overlaps happening right now
    alerts = []
    for ma_fast, ma_slow in [('SMA_200', 'SMA_500'), ('SMA_500', 'SMA_1100'), ('SMA_200', 'SMA_1100')]:
        if prev_row[ma_fast] <= prev_row[ma_slow] and last_row[ma_fast] > last_row[ma_slow]:
            alerts.append(f"🚀 Bull Cross ({ma_fast} over {ma_slow})")
        elif prev_row[ma_fast] >= prev_row[ma_slow] and last_row[ma_fast] < last_row[ma_slow]:
            alerts.append(f"⚠️ Bear Cross ({ma_fast} under {ma_slow})")
            
    alert_str = " | ".join(alerts) if alerts else "No New Cross Today"
    return f"{state} [{alert_str}]"

def find_support_resistance(df, clusters=5):
    df['Min'] = df['Low'][(df['Low'] < df['Low'].shift(5)) & (df['Low'] < df['Low'].shift(-5))]
    df['Max'] = df['High'][(df['High'] > df['High'].shift(5)) & (df['High'] > df['High'].shift(-5))]
    pivots = pd.concat([df['Min'].dropna(), df['Max'].dropna()]).values.reshape(-1, 1)
    
    if len(pivots) < clusters:
        return [], []
    
    clustering = AgglomerativeClustering(n_clusters=clusters, linkage='ward').fit(pivots)
    levels = []
    for i in range(clusters):
        levels.append(np.mean(pivots[clustering.labels_ == i]))
        
    levels.sort()
    current_price = float(df['Close'].iloc[-1].item())
    supports = [round(x, 2) for x in levels if x < current_price]
    resistances = [round(x, 2) for x in levels if x > current_price]
    return supports[-2:], resistances[:2]

def detect_delivery_spikes(df, volume_threshold=2.5):
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20']
    ratio = float(df.iloc[-1]['Vol_Ratio'].item())
    
    if ratio >= volume_threshold:
        return f"🚨 VOLUME SPIKE: {round(ratio, 2)}x normal!"
    return f"Normal ({round(ratio, 2)}x)"

if __name__ == "__main__":
    print("🔄 Initializing ETF Analysis Script...")
    results = []
    
    for ticker in ETF_TICKERS:
        df = get_etf_data(ticker)
        if df is None or len(df) < 1100:
            print(f"Skipping {ticker}: Not enough data for 1100 MA check.")
            continue
            
        df = calculate_moving_averages(df)
        ma_status = detect_crossovers(df)
        supports, resistances = find_support_resistance(df)
        delivery_status = detect_delivery_spikes(df)
        current_price = round(float(df['Close'].iloc[-1].item()), 2)
        
        results.append({
            "Date": pd.Timestamp.now().strftime('%Y-%m-%d'),
            "ETF": ticker,
            "Price": current_price,
            "Closest_Supports": str(supports),
            "Closest_Resistances": str(resistances),
            "Moving_Average_Trend": ma_status,
            "Volume_Alert": delivery_status
        })
        
    report_df = pd.DataFrame(results)
    report_df.to_csv("etf_scan_report.csv", index=False)
    print("✅ Successfully generated output data: etf_scan_report.csv")
