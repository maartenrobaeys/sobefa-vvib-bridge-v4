import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="SOBEFA VV → IB Bridge V4", page_icon="📈", layout="wide")

# Styling voor de tabel status
def color_status(val):
    if val == "SKIP ❌": color = '#ff4b4b' # Rood
    elif val == "CAUTION ⚠": color = '#ffa500' # Oranje
    elif val == "OK ✅": color = '#09ab3b' # Groen
    else: color = 'white'
    return f'color: {color}; font-weight: bold'

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

# Handmatige input voor nieuwe signalen (SSRM, SNEX, CRDO)
st.sidebar.header("🆕 Nieuwe Signalen")
new_tickers_input = st.sidebar.text_input("Voeg tickers toe (bijv: SSRM, SNEX, CRDO)", "").upper()
manual_tickers = [t.strip() for ticker in new_tickers_input.split(",") if (t := ticker.strip())]

def reconstruct_portfolio(df):
    open_trades = {}
    if 'Description' not in df.columns: return open_trades
    
    # Filter uit: OBE (TP), PARR & SMBK (SL) - deze logica kan uitgebreid worden
    blacklist = ['EHAB', 'OBE', 'PARR', 'SMBK'] 
    
    for _, row in df.iterrows():
        desc = str(row.get('Description', ''))
        if 'Buy' in desc:
            words = desc.split()
            try:
                symbol = words[words.index('of') + 1]
                if symbol in blacklist: continue
                price = float(words[words.index('at') + 1].replace('$', '').replace(',', ''))
                open_trades[symbol] = price
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
        # Reconstructie uit CSV
        open_positions = {}
        if trade_log_file:
            df_raw = pd.read_csv(trade_log_file)
            open_positions = reconstruct_portfolio(df_raw)
        
        # Voeg handmatige tickers toe
        for ticker in manual_tickers:
            if ticker not in open_positions:
                open_positions[ticker] = None # Prijs wordt live opgehaald

        if open_positions:
            tickers = list(open_positions.keys())
            with st.spinner("Live data ophalen..."):
                price_data = yf.download(tickers, period="1d", progress=False)['Close']
                # Correcte afhandeling voor enkele of meerdere tickers
                if len(tickers) == 1:
                    current_prices = {tickers: price_data.iloc[-1]} if not price_data.empty else {}
                else:
                    current_prices = price_data.iloc[-1].to_dict()

            tracker_data = []
            for ticker, vv_price in open_positions.items():
                curr_price = current_prices.get(ticker)
                
                # EHAB Check: Als prijs ontbreekt (delisted), overslaan
                if curr_price is None or np.isnan(curr_price): continue
                
                # Als geen VV prijs bekend is (nieuwe buy), gebruik huidige prijs als referentie
                ref_price = vv_price if vv_price else curr_price
                diff_pct = ((curr_price - ref_price) / ref_price) * 100
                
                status = "OK ✅"
                if diff_pct > 1.9: status = "SKIP ❌"
                elif diff_pct > 0.5: status = "CAUTION ⚠"
                
                # Berekening: Gehele getallen voor IB
                shares = int(pos_size / curr_price)
                
                tracker_data.append({
                    "Ticker": ticker,
                    "VV Prijs": f"${ref_price:.2f}" if vv_price else "NIEUW",
                    "Live Prijs": f"${curr_price:.2f}",
                    "Afwijking": f"{diff_pct:.2f}%",
                    "Status": status,
                    "Shares (IB)": shares,
                    "Allocatie": f"${(shares * curr_price):,.2f}",
                    "IB Stop": round(curr_price * (1 - (stop_loss/100)), 2),
                    "IB Target": round(curr_price * (1 + (profit_target/100)), 2)
                })
            
            # Weergave met styling
            final_df = pd.DataFrame(tracker_data)
            st.header("📊 Live Portfolio Overzicht")
            st.table(final_df.style.applymap(color_status, subset=['Status']))

            # Export
            st.header("📤 IB Order Export")
            valid_buys = final_df[final_df["Status"] != "SKIP ❌"]
            if not valid_buys.empty:
                buy_csv = valid_buys[["Ticker", "Shares (IB)"]].to_csv(index=False)
                st.download_button("⬇ Download BUY CSV voor IB", buy_csv, "ib_buy_orders.csv", "text/csv")
            else:
                st.error("Geen trades beschikbaar (alles staat op SKIP).")
    except Exception as e:
        st.error(f"Fout: {e}")
