import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="SOBEFA VV → IB Bridge", page_icon="📈", layout="wide")

st.title("📈 SOBEFA — VV → IB Bridge V4")
st.markdown("### VectorVest Intelligence → Interactive Brokers Execution Layer")

# Instellingen in de zijbalk
st.sidebar.header("⚙ Portfolio Settings")
portfolio_capital = st.sidebar.number_input("Beschikbaar kapitaal ($)", min_value=1000, value=10000, step=1000)
max_positions = st.sidebar.slider("Max open posities", min_value=1, max_value=20, value=10)
profit_target_pct = st.sidebar.number_input("Take Profit %", value=6.0, step=0.1)
stop_loss_pct = st.sidebar.number_input("Stop Loss %", value=1.9, step=0.1)

position_size_usd = portfolio_capital / max_positions
st.sidebar.metric("Positiegrootte per trade", f"${position_size_usd:,.2f}")

# Functie om portfolio te reconstrueren uit de tradehistory.csv
def reconstruct_portfolio(df):
    open_trades = {}
    if 'Description' not in df.columns:
        return open_trades
        
    for _, row in df.iterrows():
        desc = str(row.get('Description', ''))
        if 'Buy' in desc:
            words = desc.split()
            try:
                symbol = words[words.index('of') + 1]
                price_str = words[words.index('at') + 1].replace('$', '').replace(',', '')
                price = float(price_str)
                open_trades[symbol] = price
            except: continue
        elif 'Sell' in desc:
            words = desc.split()
            try:
                symbol = words[words.index('of') + 1]
                if symbol in open_trades: del open_trades[symbol]
            except: continue
    return open_trades

# Bestanden uploaden
st.header("📂 Upload VectorVest Trade History")
trade_log_file = st.file_uploader("Sleep tradehistory.csv hierheen", type=["csv"])

if trade_log_file:
    try:
        df_raw = pd.read_csv(trade_log_file)
        st.success("Data ingeladen!")
        
        open_positions = reconstruct_portfolio(df_raw)
        
        if open_positions:
            st.header("📊 Live Portfolio Tracker")
            tickers = list(open_positions.keys())
            
            with st.spinner("Live prijzen ophalen..."):
                # Verbeterde prijs-ophaling voor zowel enkele als meerdere tickers
                price_data = yf.download(tickers, period="1d", progress=False)['Close']
                if len(tickers) == 1:
                    current_prices = {tickers: price_data.iloc[-1]} if not price_data.empty else {}
                else:
                    current_prices = price_data.iloc[-1].to_dict()

            tracker_data = []
            for ticker, vv_price in open_positions.items():
                curr_price = current_prices.get(ticker)
                
                # Check of prijs geldig is voor we gaan rekenen (voorkomt de ValueError)
                if curr_price is None or np.isnan(curr_price) or curr_price <= 0:
                    curr_price = vv_price # Fallback naar VV prijs
                
                diff_pct = ((curr_price - vv_price) / vv_price) * 100
                
                status = "OK"
                if diff_pct > 1.9: status = "SKIP ❌"
                elif diff_pct > 0.5: status = "CAUTION ⚠"
                
                # Bereken shares veilig
                shares = int(position_size_usd / curr_price) if curr_price > 0 else 0
                
                tracker_data.append({
                    "Ticker": ticker,
                    "VV Prijs": round(vv_price, 2),
                    "Live Prijs": round(curr_price, 2),
                    "Afwijking %": round(diff_pct, 2),
                    "Status": status,
                    "Shares": shares,
                    "IB Stop": round(curr_price * (1 - (stop_loss_pct/100)), 2),
                    "IB Target": round(curr_price * (1 + (profit_target_pct/100)), 2)
                })
                
            st.table(pd.DataFrame(tracker_data))

            st.header("📤 IB Order Export")
            buy_orders = pd.DataFrame(tracker_data)
            valid_buys = buy_orders[buy_orders["Status"] != "SKIP ❌"]
            if not valid_buys.empty:
                buy_csv = valid_buys[["Ticker", "Shares"]].to_csv(index=False)
                st.download_button("⬇ Download BUY CSV", buy_csv, "ib_buy_orders.csv", "text/csv")
            else:
                st.info("Geen geldige kooporders (alles staat op SKIP).")
        else:
            st.warning("Geen open posities gevonden in dit bestand.")
    except Exception as e:
        st.error(f"Er ging iets mis bij het verwerken van het bestand: {e}")
