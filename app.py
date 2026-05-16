import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="SOBEFA VV → IB Bridge V4", page_icon="📈", layout="wide")

# Functie voor dynamische opacity en kleurverloop
def style_risk_columns(row):
    try:
        dev_val = float(str(row['Afwijking']).replace('%', ''))
        abs_dev = abs(dev_val)
        
        # Bereken opacity (alpha) tussen 0.1 en 0.8 op basis van afwijking
        # 1.9% is de kritieke grens voor SKIP
        alpha = min(max(abs_dev / 1.9, 0.1), 0.8)
        
        if abs_dev < 0.5:
            color = f'rgba(9, 171, 59, {alpha})' # Groen (OK)
        elif abs_dev < 1.9:
            color = f'rgba(255, 165, 0, {alpha})' # Oranje (CAUTION)
        else:
            color = f'rgba(255, 75, 75, {alpha})' # Rood (SKIP)
            
        style = f'background-color: {color}; color: black; font-weight: bold'
        return [style if col in ['Afwijking', 'Status'] else '' for col in row.index]
    except:
        return ['' for _ in row.index]

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

# Handmatige input voor nieuwe signalen
st.sidebar.header("🆕 Nieuwe Signalen")
new_tickers_input = st.sidebar.text_input("Voeg tickers toe (gescheiden door komma)", "").upper()
manual_tickers = [t.strip() for t in new_tickers_input.split(",") if t.strip()]

def clean_vv_price(price_str):
    cleaned = str(price_str).replace('$', '').replace(',', '').strip()
    try:
        price = float(cleaned)
        return price / 100 if price > 2000 else price
    except: return 0.0

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
            price_data = yf.download(tickers, period="1d", progress=False)['Close']
            current_prices = price_data.iloc[-1].to_dict() if len(tickers) > 1 else {tickers: price_data.iloc[-1]}

            tracker_data = []
            for ticker, vv_price in open_positions.items():
                curr_price = current_prices.get(ticker)
                if curr_price is None or np.isnan(curr_price): continue
                
                ref_price = vv_price if vv_price else curr_price
                diff_pct = ((curr_price - ref_price) / ref_price) * 100
                
                status = "OK ✅"
                if diff_pct > 1.9: status = "SKIP ❌"
                elif diff_pct > 0.5: status = "CAUTION ⚠"
                
                # Positie voortgang: waar staan we tussen -1.9% en +6%?
                # We schalen dit naar een waarde tussen 0 en 100 voor een visuele balk
                progress = min(max((diff_pct + stop_loss) / (profit_target + stop_loss) * 100, 0), 100)
                
                tracker_data.append({
                    "Ticker": ticker,
                    "VV Buy Price": f"${ref_price:.2f}" if vv_price else "NIEUW",
                    "Live Price": f"${curr_price:.2f}",
                    "Afwijking": f"{diff_pct:.2f}%",
                    "Status": status,
                    "Positie Tracker": progress,
                    "Shares (IB)": int(pos_size / curr_price),
                    "Allocatie": f"${(int(pos_size / curr_price) * curr_price):,.2f}"
                })
            
            final_df = pd.DataFrame(tracker_data)
            st.header("📊 Live Portfolio Overzicht")
            
            # Tabel weergeven met de nieuwe gradient styling en een progress bar
            st.dataframe(
                final_df.style.apply(style_risk_columns, axis=1),
                column_config={
                    "Positie Tracker": st.column_config.ProgressColumn(
                        "Track (SL ↔ TP)",
                        help="Visuele positie tussen -1.9% Stop Loss en +6% Take Profit",
                        format="%.0f%%",
                        min_value=0,
                        max_value=100,
                    )
                },
                use_container_width=True
            )

            st.header("📤 IB Order Export")
            valid_buys = final_df[final_df["Status"] != "SKIP ❌"]
            if not valid_buys.empty:
                buy_csv = valid_buys[["Ticker", "Shares (IB)"]].to_csv(index=False)
                st.download_button("⬇ Download BUY CSV voor IB", buy_csv, "ib_buy_orders.csv", "text/csv")
    except Exception as e:
        st.error(f"Fout: {e}")
