import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="SOBEFA VV → IB Bridge V4", page_icon="📈", layout="wide")

# Functie voor de gradient kleuren in de Afwijking kolom
def color_deviation(val):
    try:
        num = float(val.replace('%', ''))
        # Groen bij 0, Rood bij > 1.9 of < -1.9
        if abs(num) < 0.5: color = '#09ab3b' # Helder groen
        elif abs(num) < 1.9: color = '#ffa500' # Oranje
        else: color = '#ff4b4b' # Rood (SKIP)
        return f'background-color: {color}; color: white; font-weight: bold'
    except:
        return ''

st.title("📈 SOBEFA — VV → IB Bridge V4")
st.markdown("### Intelligent Execution Layer (RSI 2-Day Strategy)")

# Instellingen in de zijbalk
st.sidebar.header("⚙ Portfolio Instellingen")
portfolio_capital = st.sidebar.number_input("Totaal Budget IB ($)", min_value=1000, value=10000, step=500)
max_positions = st.sidebar.slider("Max posities", 1, 20, 10)
profit_target = st.sidebar.number_input("Take Profit %", value=6.0)
stop_loss = st.sidebar.number_input("Stop Loss %", value=1.9)

pos_size = portfolio_capital / max_positions
st.sidebar.metric("Budget per positie", f"${pos_size:,.2f}")

# Handmatige input voor SSRM, SNEX, CRDO
st.sidebar.header("🆕 Nieuwe Signalen")
new_tickers_input = st.sidebar.text_input("Voeg tickers toe (gescheiden door komma)", "").upper()
manual_tickers = [t.strip() for t in new_tickers_input.split(",") if t.strip()]

def clean_vv_price(price_str):
    """Herstelt de decimalen fout uit de VectorVest export"""
    cleaned = price_str.replace('$', '').replace(',', '').strip()
    price = float(cleaned)
    # Correctie-logica: als de prijs onwaarschijnlijk hoog is (> 5000 voor deze stocks), 
    # dan zijn de decimalen wss 100x verschoven.
    if price > 2000: # Meeste aandelen in je PF zijn rond de $10 - $400
        return price / 100
    return price

def reconstruct_portfolio(df):
    open_trades = {}
    if 'Description' not in df.columns: return open_trades
    blacklist = ['EHAB', 'OBE', 'PARR', 'SMBK'] 
    
    for _, row in df.iterrows():
        desc = str(row.get('Description', ''))
        if 'Buy' in desc:
            words = desc.split()
            try:
                symbol = words[words.index('of') + 1]
                if symbol in blacklist: continue
                raw_price = words[words.index('at') + 1]
                open_trades[symbol] = clean_vv_price(raw_price)
            except: continue
        elif 'Sell' in desc:
            words = desc.split()
            try:
                symbol = words[words.index('of') + 1]
                if symbol in open_trades: del open_trades[symbol]
            except: continue
    return open_trades

trade_log_file = st.file_uploader("Upload tradehistory.csv", type=["csv"])

if trade_log_file or manual_tickers:
    try:
        open_positions = {}
        if trade_log_file:
            df_raw = pd.read_csv(trade_log_file)
            open_positions = reconstruct_portfolio(df_raw)
        
        for ticker in manual_tickers:
            if ticker not in open_positions: open_positions[ticker] = None

        if open_positions:
            tickers = list(open_positions.keys())
            with st.spinner("Live data ophalen..."):
                price_data = yf.download(tickers, period="1d", progress=False)['Close']
                if len(tickers) == 1:
                    current_prices = {tickers: price_data.iloc[-1]}
                else:
                    current_prices = price_data.iloc[-1].to_dict()

            tracker_data = []
            for ticker, vv_price in open_positions.items():
                curr_price = current_prices.get(ticker)
                if curr_price is None or np.isnan(curr_price): continue
                
                ref_price = vv_price if vv_price else curr_price
                diff_pct = ((curr_price - ref_price) / ref_price) * 100
                
                status = "OK ✅"
                if diff_pct > 1.9: status = "SKIP ❌"
                elif diff_pct > 0.5: status = "CAUTION ⚠"
                
                shares = int(pos_size / curr_price)
                
                tracker_data.append({
                    "Ticker": ticker,
                    "VV Buy Price": f"${ref_price:.2f}" if vv_price else "NIEUW",
                    "Live Price": f"${curr_price:.2f}",
                    "Afwijking": f"{diff_pct:.2f}%",
                    "Status": status,
                    "Shares (IB)": shares,
                    "Allocatie": f"${(shares * curr_price):,.2f}",
                    "IB Stop": round(curr_price * (1 - (stop_loss/100)), 2),
                    "IB Target": round(curr_price * (1 + (profit_target/100)), 2)
                })
            
            final_df = pd.DataFrame(tracker_data)
            st.header("📊 Live Portfolio Overzicht")
            # Toepassen van de gradient op de Afwijking kolom
            st.dataframe(
                final_df.style.map(color_deviation, subset=['Afwijking']),
                use_container_width=True
            )

            st.header("📤 IB Order Export")
            valid_buys = final_df[final_df["Status"] != "SKIP ❌"]
            if not valid_buys.empty:
                buy_csv = valid_buys[["Ticker", "Shares (IB)"]].to_csv(index=False)
                st.download_button("⬇ Download BUY CSV voor IB", buy_csv, "ib_buy_orders.csv", "text/csv")
    except Exception as e:
        st.error(f"Fout: {e}")
