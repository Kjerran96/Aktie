import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
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

# --- Sökmotor för företagsnamn ---
def search_ticker_by_name(query):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=10"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        results = []
        for quote in data.get('quotes', []):
            symbol = quote.get('symbol')
            name = quote.get('shortname', quote.get('longname', 'Okänt namn'))
            exch = quote.get('exchDisp', 'Okänd börs')
            if symbol:
                results.append(f"{symbol} - {name} ({exch})")
        return results
    except Exception:
        return []

# --- Smart insiktsgenerator (Risker & Möjligheter) ---
def generate_insights(pe, peg, div, rsi, ma50, ma200, beta):
    positives = []
    risks = []
    
    # Värdering
    if pe is not None and pe > 0:
        if pe < 15: positives.append("Låg värdering (P/E under 15) i förhållande till dagens vinst. Aktien kan vara prisvärd.")
        elif pe > 30: risks.append("Mycket hög värdering (P/E över 30). Marknaden kräver enorm vinsttillväxt, vilket gör aktien känslig för besvikelser.")
        
    if peg is not None and peg > 0:
        if peg < 1.0: positives.append("Bolaget växer snabbt i förhållande till sin prislapp (PEG under 1.0).")
        elif peg > 2.0: risks.append("Tillväxttakten motiverar kanske inte den höga prislappen just nu (PEG över 2.0).")
        
    # Utdelning
    if div is not None and div > 0.03:
        positives.append(f"Hög direktavkastning ({round(div*100,1)}%). Ger en stabil krockkudde i portföljen även om börsen står stilla.")
    elif div is None or div == 0:
        risks.append("Ger ingen utdelning. Hela din framtida avkastning hänger på att själva aktiekursen går upp.")
        
    # Trend
    if ma50 is not None and ma200 is not None:
        if ma50 > ma200: positives.append("Teknisk styrka: Aktien befinner sig i en långsiktig uppåttrend (Golden Cross).")
        else: risks.append("Teknisk svaghet: Aktien befinner sig i en långsiktig nedåttrend. Kan vara riskfyllt att 'fånga en fallande kniv'.")
        
    # Momentum
    if rsi is not None:
        if rsi < 30: positives.append("Kortsiktigt översåld. Säljarna kan ha tryckt ner priset för mycket den senaste tiden.")
        elif rsi > 70: risks.append("Kortsiktigt överköpt. Aktien har gått väldigt starkt på sistone, risk för en tillfällig rekyl nedåt.")
        
    # Volatilitet (Beta)
    if beta is not None and beta > 1.3:
        risks.append("Hög volatilitet (Beta över 1.3). Aktien kommer sannolikt svänga betydligt kraftigare än resten av börsen.")
        
    if not positives: positives.append("Hittar inga extremt utmärkande styrkor i den rena datan just nu.")
    if not risks: risks.append("Hittar inga uppenbara röda flaggor eller extremvärden i datan.")
        
    return positives, risks

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
        if macd_diff > 0: score += 15; details['MACD'] = "15 p (Positiv trend)"
        else: details['MACD'] = "0 p (Negativ trend)"
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

def fetch_stock_data(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    
    if 'shortName' not in info:
        return None
        
    pe = info.get('trailingPE', None)
    peg = info.get('pegRatio', info.get('trailingPegRatio', None))
    div = info.get('dividendYield', None)
    beta = info.get('beta', None)
    recommendation = info.get('recommendationKey', None)
    
    rsi, macd_diff, ma50, ma200 = get_technical_indicators(ticker_symbol)
    score, breakdown = calculate_score_100(pe, peg, div, recommendation, rsi, macd_diff, ma50, ma200)
    positives, risks = generate_insights(pe, peg, div, rsi, ma50, ma200, beta)
    
    return {
        'info': info, 'score': score, 'breakdown': breakdown, 
        'pe': pe, 'peg': peg, 'div': div, 'rsi': rsi, 'ma50': ma50, 'ma200': ma200,
        'positives': positives, 'risks': risks
    }

# --- Streamlit Gränssnitt ---
st.set_page_config(page_title="Aktierankaren Pro", page_icon="📈", layout="centered")

# Lösningen på att appen glömde sökningen: Session State
if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = None
if 'stock_data' not in st.session_state:
    st.session_state.stock_data = None

tab1, tab2 = st.tabs(["🔍 Sök & Analysera", "⭐ Min Sparlista"])

with tab1:
    st.title("📈 Aktierankaren")
    st.write("Sök på ett företagsnamn (t.ex. Google eller Investor).")

    name_query = st.text_input("Skriv företagsnamn eller ticker:", "")
    
    if name_query:
        suggestions = search_ticker_by_name(name_query)
        if suggestions:
            selected_option = st.selectbox("Välj rätt aktie från listan:", suggestions)
            ticker_to_analyze = selected_option.split(" - ")[0]
            
            if st.button("Hämta Ranking"):
                with st.spinner(f"Analyserar {ticker_to_analyze}..."):
                    # Spara i minnet så att knappar inuti fungerar
                    st.session_state.current_ticker = ticker_to_analyze
                    st.session_state.stock_data = fetch_stock_data(ticker_to_analyze)
        else:
            st.warning("Hittade inga aktier med det namnet.")

    # Om vi har data i minnet, visa den!
    if st.session_state.current_ticker and st.session_state.stock_data:
        data = st.session_state.stock_data
        ticker = st.session_state.current_ticker
        
        st.markdown("---")
        st.header(data['info'].get('shortName', ticker))
        
        # Sparlistan fungerar nu eftersom den inte nollställer sökningen
        watchlist = load_watchlist()
        if ticker not in watchlist:
            if st.button("⭐ Spara till Watchlist", key="save_btn"):
                watchlist.append(ticker)
                save_watchlist(watchlist)
                st.success(f"{ticker} sparades i din lista!")
                st.rerun()
        else:
            st.info("⭐ Sparad i din Watchlist")

        # Visa poäng
        score = data['score']
        color = "green" if score >= 75 else "orange" if score >= 50 else "red"
        st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 80px;'>{score} / 100</h1>", unsafe_allow_html=True)

        # Risker och möjligheter
        st.markdown("### 💡 Insikter om aktien")
        col_pos, col_neg = st.columns(2)
        with col_pos:
            st.success("**Möjligheter (Pro):**\n" + "\n".join([f"- {p}" for p in data['positives']]))
        with col_neg:
            st.error("**Risker (Con):**\n" + "\n".join([f"- {r}" for r in data['risks']]))

        # Datasammanfattning
        st.markdown("### 📊 Uppdelning av data")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Poängfördelning")
            for k, v in data['breakdown'].items():
                st.write(f"**{k}:** {v}")
        with col2:
            st.subheader("Rådata")
            pe_val = data['pe']
            peg_val = data['peg']
            div_val = data['div']
            rsi_val = data['rsi']
            ma50_val = data['ma50']
            ma200_val = data['ma200']
            
            st.write(f"- **P/E:** {round(pe_val, 2) if pe_val else '-'}")
            st.write(f"- **PEG:** {round(peg_val, 2) if peg_val else '-'}")
            st.write(f"- **Utdelning:** {round(div_val * 100, 2) if div_val else 0}%")
            st.write(f"- **RSI (14):** {round(rsi_val, 2) if rsi_val else '-'}")
            st.write(f"- **MA50/MA200:** {round(ma50_val, 2) if ma50_val else '-'} / {round(ma200_val, 2) if ma200_val else '-'}")

with tab2:
    st.title("⭐ Min Sparlista")
    st.write("Här är dina sparade aktier. Tryck på knappen nedan för att räkna ut dagens poäng.")
    
    watchlist = load_watchlist()
    
    if len(watchlist) == 0:
        st.write("Din sparlista är tom.")
    else:
        if st.button("🔄 Uppdatera alla poäng nu"):
            for ticker_symbol in watchlist:
                with st.spinner(f"Hämtar data för {ticker_symbol}..."):
                    data = fetch_stock_data(ticker_symbol)
                    
                    if data:
                        with st.expander(f"{ticker_symbol} - {data['info'].get('shortName', '')} (Poäng: {data['score']}/100)"):
                            score = data['score']
                            color = "green" if score >= 75 else "orange" if score >= 50 else "red"
                            st.markdown(f"<h3 style='color: {color};'>{score} / 100</h3>", unsafe_allow_html=True)
                            
                            col_pos, col_neg = st.columns(2)
                            with col_pos:
                                st.success("\n".join([f"- {p}" for p in data['positives']]))
                            with col_neg:
                                st.error("\n".join([f"- {r}" for r in data['risks']]))
                            
                            if st.button(f"Ta bort {ticker_symbol} från listan", key=f"del_{ticker_symbol}"):
                                watchlist.remove(ticker_symbol)
                                save_watchlist(watchlist)
                                st.rerun()
