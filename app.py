import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="SOBEFA VV → IB Bridge V4", page_icon="📈", layout="wide")

# Subtiele styling functie
def style_subtle_risk(row):
    try:
        dev_val = float(str(row['Afwijking']).replace('%', ''))
        abs_dev = abs(dev_val)
        alpha = min(max(abs_dev / 1.9 * 0.3, 0.05), 0.3)
        if abs_dev < 0.5: color = f'rgba(9, 171, 59, {alpha})'
        elif abs_dev < 1.9: color = f'rgba(255, 165, 0, {alpha})'
        else: color = f'rgba(255, 75, 75, {alpha})'
        return [f'background-color: {color}; color: #333' if col in ['Afwijking', 'Status'] else '' for col in row.index]
    except: return ['' for _ in row.index]

st.title("📈 SOBEFA — VV → IB Bridge V4")
st.markdown("### Intelligent Execution Layer — RSI 2-Day Strategy")

# Zijbalk met compounding-input
st.sidebar.header("⚙ Portfolio Instellingen")
portfolio_capital = st.sidebar.number_input("Totaal Budget IB ($)", min_value=1000, value=10000, step=500)
max_positions = st.sidebar.slider("Max posities", 1, 20, 10)
profit_target = st.sidebar.number_input("Take Profit %", value=6.0)
stop_loss = st.sidebar.number_input("Stop Loss %", value=1.9)

pos_size = portfolio_capital / max_positions
st.sidebar.metric("Budget per positie", f"${pos_size:,.2f}")

st.sidebar.header("🆕 Nieuwe Signalen")
new_tickers_input = st.sidebar.text_input("Voeg tickers toe (bijv: SSRM, SNEX, CRDO)", "").upper()
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
                open_trades[symbol] = clean_vv_price(words[words.index('at') + 1])
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
                
                sl_prog = min(max(diff_pct / -stop_loss * 100, 0), 100) if diff_pct < 0 else 0
                tp_prog = min(max(diff_pct / profit_target * 100, 0), 100) if diff_pct > 0 else 0
                
                tracker_data.append({
                    "Ticker": ticker, "VV Buy": f"${ref_price:.2f}", "Live": f"${curr_price:.2f}",
                    "Afwijking": f"{diff_pct:.2f}%", "Status": status,
                    "Track SL": sl_prog, "Track TP": tp_prog, "Shares": int(pos_size / curr_price)
                })
            
            st.header("📊 Live Portfolio Overzicht")
            st.dataframe(
                pd.DataFrame(tracker_data).style.apply(style_subtle_risk, axis=1),
                column_config={
                    "Track SL": st.column_config.ProgressColumn("📉 Track SL", format="%.0f%%", min_value=0, max_value=100, color="red"),
                    "Track TP": st.column_config.ProgressColumn("🚀 Track TP", format="%.0f%%", min_value=0, max_value=100, color="green")
                }, use_container_width=True
            )

        # --- NIEUW: COMPOUND GROWTH SIMULATION ---
        st.markdown("---")
        st.header("📈 CAGR & Compounding Simulator")
        col1, col2 = st.columns(2)
        with col1:
            years = st.slider("Looptijd in jaren", 1, 30, 20)
            target_cagr = st.slider("Verwachte CAGR %", 1.0, 30.0, 10.7) # 10.7 is de 30-jarige VV RSI-historie [1]
        
        capital_curve = []
        cap = portfolio_capital
        for year in range(years + 1):
            capital_curve.append({"Jaar": year, "Kapitaal": cap})
            cap *= (1 + (target_cagr / 100))
        
        fig = px.line(pd.DataFrame(capital_curve), x="Jaar", y="Kapitaal", 
                      title=f"Projectie: Groei naar ${(cap/(1 + target_cagr/100)):,.0f} over {years} jaar")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Fout: {e}")
