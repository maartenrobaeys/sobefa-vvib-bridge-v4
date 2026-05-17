import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# --- CONFIGURATIE & STYLING (Deel 1, 2 & 14) ---
st.set_page_config(page_title="SOBEFA Master Bridge V5.3", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8fafc; color: #1e293b; }
    .sec-hdr { padding: 8px 12px; border-radius: 5px; font-weight: 800; color: white; margin-top: 20px; font-size: 13px; }
    .sec-blue { background: #1e3a5f; }
    .sec-green { background: #0f6e56; }
    .stMetric { background-color: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; }
    .log-ok { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 10px; border-radius: 8px; font-weight: bold; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- REKEN ENGINES ---
def clean_vv_price(price_str):
    try:
        val = float(str(price_str).replace('$', '').replace(',', '').strip())
        return val / 100 if val > 2000 else val
    except: return 0.0

def get_risk_badge(dev):
    if dev > 1.9: return "❌ SKIP"
    if dev > 1.0: return "⚠ Let op"
    if dev > 0.5: return "⚡ Check"
    return "✅ OK"

# --- DATA PARSER ---
def reconstruct_portfolio(df):
    open_trades, closed_trades = {}, []
    if 'Description' not in df.columns: return {}, []
    blacklist = ['EHAB', 'OBE', 'PARR', 'SMBK']
    for _, row in df.iterrows():
        desc, date = str(row['Description']), row.get('Trade Date', '—')
        if 'Buy' in desc:
            try:
                ticker = desc.split('of ')[7].split(' at')
                price = clean_vv_price(desc.split('$')[7])
                if ticker in blacklist:
                    closed_trades.append({"Ticker": ticker, "Datum": date, "VV Prijs": price, "Reden": "System Exit"})
                else: open_trades[ticker] = {"vv_p": price, "date": date}
            except: continue
        elif 'Sell' in desc:
            try:
                ticker = desc.split('of ')[7].split(' at')
                if ticker in open_trades:
                    closed_trades.append({"Ticker": ticker, "Datum": date, "VV Prijs": open_trades[ticker]['vv_p'], "Reden": "Manual Sell"})
                    del open_trades[ticker]
            except: continue
    return open_trades, closed_trades

# --- UI HEADER ---
st.title("🏆 SOBEFA Master Bridge — RSI 2-Day Strategy")
st.markdown("#### *Combined Intelligence: VectorVest Portfolio → Interactive Brokers Execution*")

# --- SIDEBAR & SETTINGS ---
st.sidebar.header("⚙️ Instellingen")
capital = st.sidebar.number_input("💰 Kapitaal ($)", value=10000, step=500)
max_pos = st.sidebar.slider("📊 Max posities", 1, 20, 10)
pos_size = capital / max_pos
st.sidebar.metric("Budget per positie", f"${pos_size:,.2f}")

new_input = st.sidebar.text_input("🆕 Nieuwe Signalen (bijv: SSRM, SNEX)", "").upper()
manual_tickers = [t.strip() for t in new_input.split(",") if t.strip()]

# --- DATA VERWERKING ---
file = st.file_uploader("📂 Upload tradehistory.csv", type=["csv"])

if file or manual_tickers:
    try:
        raw_open, closed_list = reconstruct_portfolio(pd.read_csv(file)) if file else ({}, [])
        for t in manual_tickers:
            if t not in raw_open: raw_open[t] = {"vv_p": None, "date": "VANDAAG"}

        if raw_open:
            tickers = list(raw_open.keys())
            with st.spinner("🔄 Koersen ophalen..."):
                data = yf.download(tickers, period="1d", progress=False)['Close']
                prices = data.iloc[-1].to_dict() if len(tickers) > 1 else {tickers: data.iloc[-1]}
            
            ts = datetime.now().strftime("%H:%M")
            st.markdown(f"<div class='log-ok'>✅ {len(tickers)} koersen geladen — {ts} (Yahoo Finance, ~15 min vertraagd)</div>", unsafe_allow_html=True)

            master_data = []
            for t, info in raw_open.items():
                curr = prices.get(t, 0.0)
                vv_p = info['vv_p'] if info['vv_p'] else curr
                dev_pct = ((curr - vv_p) / vv_p * 100) if vv_p > 0 else 0.0
                
                master_data.append({
                    "Ticker": t, "Type": "Bestaand" if info['vv_p'] else "NIEUW",
                    "Datum": info['date'], "VV Prijs": vv_p,
                    "IB Prijs ✏️": curr, "Dev %": round(dev_pct, 2),
                    "Status": get_risk_badge(dev_pct),
                    "Jij verdient": round(((vv_p * 1.06 - curr) / curr * 100), 2) if curr > 0 else 0.0,
                    "Jij verliest": round(((vv_p * 0.981 - curr) / curr * 100), 2) if curr > 0 else 0.0,
                    "Shares": int(pos_size / curr) if curr > 0 else 0,
                    "SL←│→TP": min(max(dev_pct, -1.9), 6.0)
                })

            df_master = pd.DataFrame(master_data)
            st.markdown("<div class='sec-hdr sec-blue'>📂 PORTFOLIO OVERZICHT & EXECUTIE MONITOR</div>", unsafe_allow_html=True)
            
            edited_df = st.data_editor(
                df_master,
                column_config={
                    "IB Prijs ✏️": st.column_config.NumberColumn(format="$%.2f"),
                    "SL←│→TP": st.column_config.ProgressColumn("Monitor", min_value=-1.9, max_value=6.0, format="%.1f%%"),
                    "Jij verdient": st.column_config.NumberColumn("Bij VV TP", format="%.1f%%"),
                    "Jij verliest": st.column_config.NumberColumn("Bij VV SL", format="%.1f%%"),
                },
                disabled=["Ticker", "Type", "Datum", "VV Prijs", "Dev %", "Status", "Shares"],
                hide_index=True, use_container_width=True
            )

            # CSV Download voor IB
            csv_data = edited_df[["Ticker", "Shares"]].to_csv(index=False).encode('utf-8-sig')
            st.download_button("⬇️ Download IB BUY Orders", csv_data, "ib_buys.csv", "text/csv")

        if closed_list:
            st.markdown("<div class='sec-hdr sec-gray'>🔒 GESLOTEN POSITIES (ARCHIEF)</div>", unsafe_allow_html=True)
            st.table(pd.DataFrame(closed_list))

    except Exception as e: st.error(f"Fout: {e}")
