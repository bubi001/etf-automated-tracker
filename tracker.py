import os
import requests
import yfinance as yf

# Configure your asset tickers and corresponding % shift alert thresholds
ASSETS = {
    "Gold": {"ticker": "GC=F", "threshold": 1.5},
    "Silver": {"ticker": "SI=F", "threshold": 2.5},
    "Crude Oil": {"ticker": "CL=F", "threshold": 3.0},
    "NASDAQ 100": {"ticker": "^NDX", "threshold": 1.5},
    "GIFT Nifty": {"ticker": "^NSEIX", "threshold": 1.0}
}

def send_alert(message):
    """Dispatches a notification string to Telegram, Discord, or Slack via Webhooks."""
    # Example: Telegram Bot API Implementation
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        url = f"https://telegram.org{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to transmit alert: {e}")
    else:
        print(f"ALERT LOG (Webhook Secrets Missing):\n{message}")

def monitor_markets():
    alert_messages = []
    print("Initiating Live Price Extraction...")
    
    for name, config in ASSETS.items():
        try:
            ticker = yf.Ticker(config["ticker"])
            # Fetch near-real-time intraday data structures
            data = ticker.history(period="2d", interval="1m")
            
            if data.empty:
                # Fallback to daily data structure if intraday is out-of-market
                data = ticker.history(period="5d")
                
            if len(data) < 2:
                continue
                
            current_price = data['Close'].iloc[-1]
            previous_close = data['Close'].iloc[-2]
            percent_change = ((current_price - previous_close) / previous_close) * 100
            
            print(f"{name}: Current={current_price:.2f} | Change={percent_change:+.2f}%")
            
            # Identify big movements out of regular historical noise
            if abs(percent_change) >= config["threshold"]:
                emoji = "🚨" if percent_change < 0 else "🚀"
                alert_messages.append(
                    f"{emoji} *{name} Volatility Alert!*\n"
                    f"• Current Price: `{current_price:.2f}`\n"
                    f"• Shift: `{percent_change:+.2f}%` (Threshold: {config['threshold']}%)\n"
                )
        except Exception as e:
            print(f"Error compiling metrics for {name}: {e}")
            
    if alert_messages:
        full_payload = "\n".join(alert_messages)
        send_alert(full_payload)

if __name__ == "__main__":
    monitor_markets()
