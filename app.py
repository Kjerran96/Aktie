import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os

# --- Databas för Sparlistan ---
DB_FILE = "watchlist.json"

def load_watchlist():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return []

def save_watchlist(watchlist):
    with open(DB_FILE, "w") as f:
        json.dump(watchlist, f)

# --- Algoritmen för poängberäkning (Max 100 poäng) ---
def calculate_score_100(pe, peg, dividend, recommendation, rsi, macd_diff, ma50, ma200):
    score = 0
    details = {}

    if pe is not None and pe > 0:
        if pe < 15: score += 15; details['P/E'] = "15 p (< 15)"
        elif 15 <= pe <= 25: score += 7; details['P/E'] = "7 p (15-25)"
        else: details['P/E'] = "0 p (> 25)"
    else: details['P/E'] = "0 p (Saknas)"

    if peg is not None and peg > 0:
        if peg < 1.0: score += 15; details['PEG'] = "15 p (< 1.0)"
        elif 1.0 <= peg <= 1.5: score += 7; details['PEG'] = "7 p (1.0-1.5)"
        else: details['PEG'] = "0 p (> 1.5)"
    else: details['PEG'] = "0 p (Saknas)"

    if recommendation:
        rec = recommendation.lower()
        if 'strong_buy' in rec: score += 20; details['Analytiker'] = "20 p (Starkt köp)"
        elif 'buy' in rec: score += 15; details['Analytiker'] = "15 p (Köp)"
        elif 'hold' in rec: score += 5; details['Analytiker'] = "5 p (Behåll)"
        else: details['Analytiker'] = "0 p (Sälj)"
    else: details['Analytiker'] = "0 p (Saknas)"

    if macd_diff is not None:
        if macd_diff > 0: score += 15; details['MACD'] = "15 p (Positiv)"
        else: details['MACD'] = "0 p (Negativ)"
    else: details['MACD'] = "0 p (Saknas)"

    if ma50 is not None and ma200 is not None:
        if ma50 > ma200: score += 15; details['Golden Cross'] = "15 p (MA50 > MA200)"
        else: details['Golden Cross'] = "0 p (MA50 < MA200)"
    else: details['Golden Cross'] = "0 p (Saknas)"

    if rsi is not None:
        if rsi < 30: score += 10; details['RSI'] = "10 p (Översåld)"
        elif 30 <= rsi <= 70: score += 5; details['RSI'] = "5 p (Neutral)"
        else: details['RSI'] = "0 p (Överköpt)"
    else: details['RSI'] = "0 p (Saknas)"
        
    if dividend is not None and dividend > 0:
        score += 10; details['Utdelning'] = f"10 p ({round(dividend * 100, 2)}%)"
    else: details['Utdelning'] = "0 p (Ingen utdelning)"

    return score, details

# --- Beräkning av tekniska indikatorer ---
def get_technical_indicators(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="1y") 

    if hist.empty or len(hist) < 200:
        return None, None, None, None

    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    hist['RSI'] = 100 - (100 / (1 + rs))
    current_rsi = hist['RSI'].iloc[-1]

    exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
    exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    current_macd_diff = (macd - signal).iloc[-1]

    current_ma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
    current_ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]

    return current_rsi, current_macd_diff, current_ma50, current_ma200

def fetch_and_score(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    
    if 'shortName' not in info:
        return None, None
        
    pe_ratio = info.get('trailingPE', None)
    peg_ratio = info.get('pegRatio', info.get('trailingPegRatio', None))
    dividend = info.get('dividendYield', None)
    recommendation = info.get('recommendationKey', None)
    
    rsi, macd_diff, ma50, ma200 = get_technical_indicators(ticker_symbol)
    score, breakdown = calculate_score_100(pe_ratio, peg_ratio, dividend, recommendation, rsi, macd_diff, ma50, ma200)
    
    return info, score, breakdown, pe_ratio, peg_ratio, dividend, rsi, ma50, ma200

# --- Streamlit Gränssnitt ---
st.set_page_config(page_title="Aktierankaren Pro", page_icon="📈", layout="centered")

# Skapa flikar för Sökning och Sparlista
tab1, tab2 = st.tabs(["🔍 Sök & Analysera", "⭐ Min Sparlista"])

with tab1:
    st.title("📈 Aktierankaren")
    st.write("Sök på en aktie (t.ex. GOOGL eller INVE-B.ST).")

    search_query = st.text_input("Ticker-symbol:", "").upper()
    
    if st.button("Hämta Ranking") and search_query:
        with st.spinner(f"Analyserar {search_query}..."):
            info, score, breakdown, pe, peg, div, rsi, ma50, ma200 = fetch_and_score(search_query)
            
            if info:
                st.header(info.get('shortName', search_query))
                
                # Hantera spara-knappen
                watchlist = load_watchlist()
                if search_query not in watchlist:
                    if st.button("⭐ Spara till Watchlist"):
                        watchlist.append(search_query)
                        save_watchlist(watchlist)
                        st.success(f"{search_query} sparades i din lista!")
                else:
                    st.info("Denna aktie finns redan i din sparlista.")

                color = "green" if score >= 75 else "orange" if score >= 50 else "red"
                st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 80px;'>{score} / 100</h1>", unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Poängfördelning")
                    for k, v in breakdown.items():
                        st.write(f"**{k}:** {v}")

                with col2:
                    st.subheader("Rådata")
                    st.write(f"- **P/E:** {round(pe, 2) if pe else '-'}")
                    st.write(f"- **PEG:** {round(peg, 2) if peg else '-'}")
                    st.write(f"- **Utdelning:** {round(div * 100, 2) if div else 0}%")
                    st.write(f"- **RSI (14):** {round(rsi, 2) if rsi else '-'}")
                    st.write(f"- **MA50/MA200:** {round(ma50, 2) if ma50 else '-'} / {round(ma200, 2) if ma200 else '-'}")
            else:
                st.error("Hittade inte aktien. Kontrollera symbolen.")

with tab2:
    st.title("⭐ Min Sparlista")
    st.write("Här är dina sparade aktier. Tryck på knappen nedan för att räkna ut dagens poäng för alla.")
    
    watchlist = load_watchlist()
    
    if len(watchlist) == 0:
        st.write("Din sparlista är tom.")
    else:
        # En knapp för att uppdatera alla aktier i listan samtidigt
        if st.button("🔄 Uppdatera alla poäng nu"):
            for ticker_symbol in watchlist:
                with st.spinner(f"Hämtar data för {ticker_symbol}..."):
                    info, score, breakdown, _, _, _, _, _, _ = fetch_and_score(ticker_symbol)
                    
                    if info:
                        # Skapa en snygg box för varje sparad aktie
                        with st.expander(f"{ticker_symbol} - {info.get('shortName', '')} (Poäng: {score}/100)"):
                            color = "green" if score >= 75 else "orange" if score >= 50 else "red"
                            st.markdown(f"<h3 style='color: {color};'>{score} / 100</h3>", unsafe_allow_html=True)
                            
                            for k, v in breakdown.items():
                                st.write(f"**{k}:** {v}")
                            
                            if st.button(f"Ta bort {ticker_symbol} från listan", key=f"del_{ticker_symbol}"):
                                watchlist.remove(ticker_symbol)
                                save_watchlist(watchlist)
                                st.rerun() # Uppdaterar sidan direkt
