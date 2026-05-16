import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="SOBEFA VV → IB Bridge", page_icon="📈", layout="wide")

st.title("📈 SOBEFA — VV → IB Bridge V2")
st.markdown("### VectorVest Intelligence → Interactive Brokers Execution Layer")

# Instellingen in de zijbalk
st.sidebar.header("⚙ Portfolio Settings")
portfolio_capital = st.sidebar.number_input("Beschikbaar kapitaal ($)", min_value=1000, value=10000, step=1000)
max_positions = st.sidebar.slider("Max open posities", min_value=1, max_value=20, value=10)
profit_target_pct = st.sidebar.number_input("Take Profit %", value=6.0, step=0.1)
stop_loss_pct = st.sidebar.number_input("Stop Loss %", value=1.9, step=0.1)
ib_fee_pct = st.sidebar.number_input("IB fees schatting %", value=0.05, step=0.01)

position_size_usd = portfolio_capital / max_positions
st.sidebar.metric("Positiegrootte per trade", f"${position_size_usd:,.2f}")

# Bestanden uploaden
st.header("📂 Upload VectorVest Files")
trade_log_file = st.file_uploader("Upload Trade History (.csv)", type=["csv"])

if trade_log_file:
    df = pd.read_csv(trade_log_file)
    st.success("Bestand succesvol geladen!")
    
    # Hier komt de logica om trades te tonen en IB orders te genereren
    st.header("📊 Live Portfolio Tracker")
    st.write(df.head()) # Toont de eerste regels als preview

    # Export knoppen (Placeholder logica)
    st.header("📤 Interactive Brokers Export")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(label="⬇ Download BUY CSV", data="Symbol,Quantity,OrderType\nAAPL,10,MKT", file_name="ib_buy_orders.csv", mime="text/csv")
    with col2:
        st.download_button(label="⬇ Download STOP CSV", data="Symbol,StopPrice,OrderType\nAAPL,150.50,STP", file_name="ib_stop_orders.csv", mime="text/csv")

st.info("Handleiding: Upload tradehistory.csv -> Controleer data -> Download CSV -> Importeer in IB.")
