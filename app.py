import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
import altair as alt

# --- Databas för Portföljen (Uppgraderad) ---
DB_FILE = "watchlist.json"

def load_watchlist():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try:
                data = json.load(f)
                # Uppgradera gammal lista till ny portfölj-ordbok om nödvändigt
                if isinstance(data, list):
                    return {ticker: {"shares": 0.0, "avg_price": 0.0} for ticker in data}
                return data
            except:
                return {}
    return {}

def save_watchlist(watchlist):
    with open(DB_FILE, "w") as f:
        json.dump(watchlist, f)

# --- Teman för Top-listan ---
THEMES = {
    "🏆 Stockholmsbörsen (Top 25)": [
        "VOLV-B.ST", "INVE-B.ST", "ATCO-A.ST", "HM-B.ST", "SEB-A.ST", 
        "SHB-A.ST", "SWED-A.ST", "ERIC-B.ST", "ASSA-B.ST", "EVO.ST", 
        "HEXA-B.ST", "SAND.ST", "NIBE-B.ST", "SCA-B.ST", "TELIA.ST", 
        "ALFA.ST", "SKF-B.ST", "BOL.ST", "GETI-B.ST", "SINCH.ST",
        "KINV-B.ST", "LATB.ST", "EPI-A.ST", "INDU-C.ST", "SAAB-B.ST"
    ],
    "🌐 Nasdaq US (Top 25 Tech)": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", 
        "NFLX", "ADBE", "AMD", "INTC", "CSCO", "PEP", "AVGO", 
        "TXN", "QCOM", "COST", "AMGN", "INTU", "SBUX", "PYPL",
        "AMAT", "MU", "CRWD", "PANW"
    ],
    "🏢 Svenska Fastigheter": [
        "CAST.ST", "BALD-B.ST", "SBB-B.ST", "FABG.ST", "WALL-B.ST", 
        "NYF.ST", "DIOS.ST", "CORE-A.ST", "NP3.ST", "CATE.ST"
    ],
    "💰 Utdelningskungar": [
        "SWED-A.ST", "SEB-A.ST", "SHB-A.ST", "NDASC.ST", "TELE2.ST", 
        "TELIA.ST", "VOLV-B.ST", "SSAB-B.ST", "RESURS.ST"
    ],
    "🚀 Tillväxt & Tech (Sverige)": [
        "EVO.ST", "FORTNOX.ST", "SINCH.ST", "HMS.ST", "VITR.ST", 
        "MIPS.ST", "SECT-B.ST", "INSTAL.ST"
    ]
}

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

# --- Smarta etiketter & Insikter ---
def get_label(value, metric_type):
    if value is None or pd.isna(value): return "(Saknas)"
    if metric_type == 'pe':
        if value < 15: return "(Bra 🟢)"
        elif value <= 25: return "(Medel 🟡)"
        else: return "(Dålig 🔴)"
    elif metric_type == 'peg':
        if value < 1.0: return "(Bra 🟢)"
        elif value <= 1.5: return "(Medel 🟡)"
        else: return "(Dålig 🔴)"
    elif metric_type == 'div':
        if value > 0.03: return "(Bra 🟢)" 
        elif value > 0: return "(Medel 🟡)"
        else: return "(Dålig 🔴)"
    elif metric_type == 'rsi':
        if value < 30: return "(Bra/Översåld 🟢)"
        elif value <= 70: return "(Medel 🟡)"
        else: return "(Dålig/Överköpt 🔴)"
    elif metric_type == 'trend':
        if value > 0: return "(Bra 🟢)"
        else: return "(Dålig 🔴)"
    return ""

def generate_insights(pe, peg, div, rsi, ma50, ma200, beta):
    positives, risks = [], []
    if pe and pe > 0:
        if pe < 15: positives.append("Låg värdering (P/E under 15). Aktien kan vara prisvärd.")
        elif pe > 30: risks.append("Mycket hög värdering (P/E över 30). Känslig för besvikelser.")
    if peg and peg > 0:
        if peg < 1.0: positives.append("Bolaget växer snabbt i förhållande till sin prislapp (PEG < 1.0).")
        elif peg > 2.0: risks.append("Tillväxttakten motiverar kanske inte prislappen (PEG > 2.0).")
    if div and div > 0.03: positives.append(f"Hög direktavkastning ({round(div*100,1)}%). Ger stabil krockkudde.")
    elif not div: risks.append("Ger ingen utdelning. Avkastningen hänger helt på kursuppgång.")
    if ma50 and ma200:
        if ma50 > ma200: positives.append("Teknisk styrka: Långsiktig uppåttrend (Golden Cross).")
        else: risks.append("Teknisk svaghet: Långsiktig nedåttrend.")
    if rsi:
        if rsi < 30: positives.append("Kortsiktigt översåld. Kan finnas köpläge.")
        elif rsi > 70: risks.append("Kortsiktigt överköpt. Risk för tillfällig rekyl nedåt.")
    if beta and beta > 1.3: risks.append("Hög volatilitet (Beta över 1.3). Svänger mer än börsen.")
    if not positives: positives.append("Hittar inga utmärkande styrkor.")
    if not risks: risks.append("Hittar inga uppenbara röda flaggor.")
    return positives, risks

# --- Algoritmen (1-100) ---
def calculate_score_100(pe, peg, dividend, recommendation, rsi, macd_diff, ma50, ma200):
    score = 0
    details = {}
    if pe and pe > 0:
        if pe < 15: score += 15; details['P/E'] = "15 p"
        elif pe <= 25: score += 7; details['P/E'] = "7 p"
        else: details['P/E'] = "0 p"
    else: details['P/E'] = "0 p"
    if peg and peg > 0:
        if peg < 1.0: score += 15; details['PEG'] = "15 p"
        elif peg <= 1.5: score += 7; details['PEG'] = "7 p"
        else: details['PEG'] = "0 p"
    else: details['PEG'] = "0 p"
    if recommendation and isinstance(recommendation, str):
        rec = recommendation.lower()
        if 'strong_buy' in rec: score += 20; details['Analytiker'] = "20 p"
        elif 'buy' in rec: score += 15; details['Analytiker'] = "15 p"
        elif 'hold' in rec: score += 5; details['Analytiker'] = "5 p"
        else: details['Analytiker'] = "0 p"
    else: details['Analytiker'] = "0 p"
    if macd_diff:
        if macd_diff > 0: score += 15; details['MACD'] = "15 p"
        else: details['MACD'] = "0 p"
    else: details['MACD'] = "0 p"
    if ma50 and ma200:
        if ma50 > ma200: score += 15; details['Golden Cross'] = "15 p"
        else: details['Golden Cross'] = "0 p"
    else: details['Golden Cross'] = "0 p"
    if rsi:
        if rsi < 30: score += 10; details['RSI'] = "10 p"
        elif rsi <= 70: score += 5; details['RSI'] = "5 p"
        else: details['RSI'] = "0 p"
    else: details['RSI'] = "0 p"
    if dividend and dividend > 0: score += 10; details['Utdelning'] = "10 p"
    else: details['Utdelning'] = "0 p"
    return score, details

def safe_val(val):
    if pd.isna(val): return None
    return float(val)

# --- Historisk Tidsmaskin ---
def get_historical_scores(ticker_symbol, current_pe, current_peg, dividend, recommendation):
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="2y")
    if hist.empty or len(hist) < 200: return None
    
    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    hist['RSI'] = 100 - (100 / (1 + rs))
    
    exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
    exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
    hist['MACD_Diff'] = (exp1 - exp2) - (exp1 - exp2).ewm(span=9, adjust=False).mean()
    hist['MA50'] = hist['Close'].rolling(window=50).mean()
    hist['MA200'] = hist['Close'].rolling(window=200).mean()
    
    try: monthly_data = hist.resample('ME').last().tail(12)
    except: monthly_data = hist.resample('M').last().tail(12)
    
    current_price = safe_val(hist['Close'].iloc[-1])
    eps = current_price / current_pe if (current_price and current_pe and current_pe > 0) else None
    
    swe_months = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Maj", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dec"}
    history_dict = {}
    
    for date, row in monthly_data.iterrows():
        close_price = safe_val(row['Close'])
        if not close_price: continue
        hist_pe = close_price / eps if eps else None
        hist_div = (dividend * current_price) / close_price if (dividend and current_price) else None
        hist_peg = current_peg * (hist_pe / current_pe) if (current_peg and current_pe and current_pe > 0 and hist_pe) else None
        s, _ = calculate_score_100(hist_pe, hist_peg, hist_div, recommendation, safe_val(row['RSI']), safe_val(row['MACD_Diff']), safe_val(row['MA50']), safe_val(row['MA200']))
        month_str = f"{swe_months[date.month]} '{str(date.year)[-2:]}"
        history_dict[month_str] = s
        
    return history_dict

# --- Huvudfunktion för datainsamling ---
def fetch_stock_data(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    if 'shortName' not in info: return None
        
    pe = info.get('trailingPE', None)
    peg = info.get('pegRatio', info.get('trailingPegRatio', None))
    div = info.get('dividendYield', None)
    beta = info.get('beta', None)
    recommendation = info.get('recommendationKey', None)
    current_price = info.get('currentPrice', info.get('regularMarketPrice', None))
    
    try: news = ticker.news[:3] # Hämta 3 senaste nyheterna
    except: news = []
    
    hist_5y_data = ticker.history(period="5y")
    hist_5y = hist_5y_data['Close'] if not hist_5y_data.empty else pd.Series()
    if not current_price and not hist_5y.empty:
        current_price = hist_5y.iloc[-1]
    
    hist_1y = ticker.history(period="1y") 
    rsi = macd_diff = ma50 = ma200 = None
    if not hist_1y.empty and len(hist_1y) >= 200:
        delta = hist_1y['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = safe_val((100 - (100 / (1 + gain/loss))).iloc[-1])
        exp1 = hist_1y['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist_1y['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        macd_diff = safe_val((macd - macd.ewm(span=9, adjust=False).mean()).iloc[-1])
        ma50 = safe_val(hist_1y['Close'].rolling(window=50).mean().iloc[-1])
        ma200 = safe_val(hist_1y['Close'].rolling(window=200).mean().iloc[-1])

    score, breakdown = calculate_score_100(pe, peg, div, recommendation, rsi, macd_diff, ma50, ma200)
    positives, risks = generate_insights(pe, peg, div, rsi, ma50, ma200, beta)
    historical_scores = get_historical_scores(ticker_symbol, pe, peg, div, recommendation)
    
    return {
        'info': info, 'score': score, 'breakdown': breakdown, 'pe': pe, 'peg': peg, 'div': div, 'rsi': rsi, 
        'ma50': ma50, 'ma200': ma200, 'positives': positives, 'risks': risks, 'hist_5y': hist_5y, 
        'historical_scores': historical_scores, 'ticker': ticker_symbol, 'current_price': current_price, 'news': news
    }

# --- Streamlit Gränssnitt ---
st.set_page_config(page_title="Aktierankaren Pro Max", page_icon="📈", layout="centered")

# --- Sessionsminnen ---
if 'stock_data' not in st.session_state: st.session_state.stock_data = None
if 'current_ticker' not in st.session_state: st.session_state.current_ticker = None
if 'search_options' not in st.session_state: st.session_state.search_options = []
if 'portfolio_data' not in st.session_state: st.session_state.portfolio_data = {}
if 'toplist_results' not in st.session_state: st.session_state.toplist_results = []
if 'duel_data_1' not in st.session_state: st.session_state.duel_data_1 = None
if 'duel_data_2' not in st.session_state: st.session_state.duel_data_2 = None

# --- De 4 Flikarna ---
tab1, tab2, tab3, tab4 = st.tabs(["🔍 Sök & Analysera", "⚔️ Duellen", "💼 Min Portfölj", "🎯 Temascanner"])

# === FLIK 1: Sök & Analysera ===
with tab1:
    st.title("📈 Aktierankaren")
    
    with st.form("search_form"):
        name_query = st.text_input("1. Sök företagsnamn eller ticker:", "")
        if st.form_submit_button("Sök i registret") and name_query:
            with st.spinner("Letar..."):
                st.session_state.search_options = search_ticker_by_name(name_query)

    if st.session_state.search_options:
        selected_option = st.selectbox("2. Välj rätt aktie:", st.session_state.search_options)
        ticker_to_analyze = selected_option.split(" - ")[0]
        
        if st.button("Hämta Ranking", type="primary"):
            with st.spinner(f"Analyserar {ticker_to_analyze}..."):
                st.session_state.current_ticker = ticker_to_analyze
                st.session_state.stock_data = fetch_stock_data(ticker_to_analyze)

    if st.session_state.current_ticker and st.session_state.stock_data:
        data = st.session_state.stock_data
        ticker = st.session_state.current_ticker
        
        st.markdown("---")
        st.header(data['info'].get('shortName', ticker))
        
        watchlist = load_watchlist()
        if ticker not in watchlist:
            if st.button("⭐ Lägg till i Portfölj / Bevakning"):
                watchlist[ticker] = {"shares": 0.0, "avg_price": 0.0}
                save_watchlist(watchlist)
                st.success("Sparad!")
                st.rerun()
        else:
            st.info("⭐ Finns i din portfölj")

        score = data['score']
        color = "green" if score >= 75 else "orange" if score >= 50 else "red"
        st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 80px;'>{score} / 100</h1>", unsafe_allow_html=True)

        col_pos, col_neg = st.columns(2)
        with col_pos: st.success("**Möjligheter:**\n" + "\n".join([f"- {p}" for p in data['positives']]))
        with col_neg: st.error("**Risker:**\n" + "\n".join([f"- {r}" for r in data['risks']]))

        # NYHETER
        if data['news']:
            st.markdown("### 📰 Senaste Nyheterna")
            for n in data['news']:
                title = n.get('title', 'Nyhet')
                link = n.get('link', '#')
                publisher = n.get('publisher', 'Nyhetskälla')
                st.markdown(f"- [{title}]({link}) *(Källa: {publisher})*")

        st.markdown("### 📊 Uppdelning av data")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**P/E:** {round(data['pe'], 2) if data['pe'] else '-'} {get_label(data['pe'], 'pe')}")
            st.write(f"**PEG:** {round(data['peg'], 2) if data['peg'] else '-'} {get_label(data['peg'], 'peg')}")
            st.write(f"**Utdelning:** {round(data['div'] * 100, 2) if data['div'] else 0}% {get_label(data['div'], 'div')}")
            st.write(f"**RSI (14):** {round(data['rsi'], 0) if data['rsi'] else '-'} {get_label(data['rsi'], 'rsi')}")
        with col2:
            for k, v in data['breakdown'].items(): st.write(f"**{k}:** {v}")

        st.markdown("---")
        if data['historical_scores']:
            st.markdown("### 📅 Poänghistorik")
            hist_df = pd.DataFrame({'Månad': list(data['historical_scores'].keys()), 'Poäng': list(data['historical_scores'].values())})
            st.altair_chart(alt.Chart(hist_df).mark_bar(color='#2ecc71').encode(x=alt.X('Månad', sort=None, title=''), y=alt.Y('Poäng', scale=alt.Scale(domain=[0, 100]))), use_container_width=True)

# === FLIK 2: Aktie-Duellen ===
with tab2:
    st.title("⚔️ Aktie-Duellen")
    st.write("Skriv in två exakta Tickers (t.ex. INVE-B.ST och LATB.ST) för att jämföra dem.")
    
    col1, col2 = st.columns(2)
    with col1: ticker1 = st.text_input("Aktie 1 (Ticker):", "INVE-B.ST").upper()
    with col2: ticker2 = st.text_input("Aktie 2 (Ticker):", "LATB.ST").upper()
    
    if st.button("Låt striden börja! 🥊", type="primary"):
        with st.spinner("Analyserar kombattanterna..."):
            st.session_state.duel_data_1 = fetch_stock_data(ticker1)
            st.session_state.duel_data_2 = fetch_stock_data(ticker2)
            
    if st.session_state.duel_data_1 and st.session_state.duel_data_2:
        d1 = st.session_state.duel_data_1
        d2 = st.session_state.duel_data_2
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        
        # Spelare 1
        with c1:
            st.subheader(d1['info'].get('shortName', d1['ticker']))
            c_color1 = "green" if d1['score'] >= d2['score'] else "red"
            st.markdown(f"<h2 style='color: {c_color1};'>{d1['score']} / 100</h2>", unsafe_allow_html=True)
            st.write(f"**P/E:** {round(d1['pe'], 1) if d1['pe'] else '-'}")
            st.write(f"**Utdelning:** {round(d1['div']*100, 1) if d1['div'] else 0}%")
            st.write(f"**RSI:** {round(d1['rsi'], 0) if d1['rsi'] else '-'}")
            
        # Spelare 2
        with c2:
            st.subheader(d2['info'].get('shortName', d2['ticker']))
            c_color2 = "green" if d2['score'] >= d1['score'] else "red"
            st.markdown(f"<h2 style='color: {c_color2};'>{d2['score']} / 100</h2>", unsafe_allow_html=True)
            st.write(f"**P/E:** {round(d2['pe'], 1) if d2['pe'] else '-'}")
            st.write(f"**Utdelning:** {round(d2['div']*100, 1) if d2['div'] else 0}%")
            st.write(f"**RSI:** {round(d2['rsi'], 0) if d2['rsi'] else '-'}")
            
        st.markdown("---")
        # Vinnare text
        if d1['score'] > d2['score']: st.success(f"🏆 Vinnare: {d1['info'].get('shortName', d1['ticker'])}")
        elif d2['score'] > d1['score']: st.success(f"🏆 Vinnare: {d2['info'].get('shortName', d2['ticker'])}")
        else: st.info("Oavgjort!")

# === FLIK 3: Min Portfölj ===
with tab2: # Actually Tab 3 in logical order, defined in with tab3:
    pass
with tab3:
    st.title("💼 Min Portfölj & Bevakning")
    
    watchlist = load_watchlist()
    
    if not watchlist:
        st.write("Din lista är tom.")
    else:
        if st.button("🔄 Uppdatera live-kurser & poäng"):
            for ticker in watchlist.keys():
                with st.spinner(f"Hämtar data för {ticker}..."):
                    res = fetch_stock_data(ticker)
                    if res: st.session_state.portfolio_data[ticker] = res

        st.markdown("---")
        
        for ticker, user_data in list(watchlist.items()):
            data = st.session_state.portfolio_data.get(ticker)
            
            with st.expander(f"{ticker} (Klicka för att hantera innehav)"):
                col_info, col_math, col_action = st.columns([4, 3, 2])
                
                with col_info:
                    if data:
                        name = data['info'].get('shortName', ticker)
                        score = data['score']
                        clr = "green" if score >= 75 else "orange" if score >= 50 else "red"
                        st.markdown(f"**{name}**")
                        st.markdown(f"Algoritmpoäng: <span style='color:{clr}; font-weight:bold;'>{score}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**{ticker}** (Klicka uppdatera för data)")
                        
                with col_math:
                    new_shares = st.number_input("Antal aktier:", min_value=0.0, value=float(user_data.get("shares", 0.0)), key=f"sh_{ticker}")
                    new_avg = st.number_input("Ditt GAV (Snittpris):", min_value=0.0, value=float(user_data.get("avg_price", 0.0)), key=f"gav_{ticker}")
                    
                    # Räkna ut vinst/förlust om data finns
                    if data and data['current_price'] and new_shares > 0 and new_avg > 0:
                        total_invested = new_shares * new_avg
                        current_value = new_shares * data['current_price']
                        profit = current_value - total_invested
                        profit_pct = (profit / total_invested) * 100
                        p_color = "green" if profit >= 0 else "red"
                        st.markdown(f"**Utveckling:** <span style='color:{p_color};'>{round(profit_pct, 2)}%</span>", unsafe_allow_html=True)
                        st.markdown(f"**Värde:** {round(current_value, 0)} kr")
                
                with col_action:
                    # Spara-knapp för innehavet
                    if st.button("💾 Spara innehav", key=f"sav_{ticker}"):
                        watchlist[ticker]["shares"] = new_shares
                        watchlist[ticker]["avg_price"] = new_avg
                        save_watchlist(watchlist)
                        st.success("Sparat!")
                    
                    if st.button("❌ Ta bort helt", key=f"del_{ticker}"):
                        del watchlist[ticker]
                        save_watchlist(watchlist)
                        st.rerun()

# === FLIK 4: Temascanner ===
with tab4:
    st.title("🎯 Temascanner")
    st.write("Skanna specifika marknader eller teman (t.ex. Svenska Fastigheter) för att hitta vinnarna just nu.")
    
    theme_choice = st.selectbox("Välj tema:", list(THEMES.keys()))
    
    if st.button("🔍 Skanna Temat", type="primary"):
        tickers_to_scan = THEMES[theme_choice]
        my_bar = st.progress(0, text="Skannar bolagen...")
        
        results = []
        for i, ticker in enumerate(tickers_to_scan):
            data = fetch_stock_data(ticker)
            if data: results.append(data)
            my_bar.progress((i + 1) / len(tickers_to_scan), text=f"Analyserar {ticker} ({i+1}/{len(tickers_to_scan)})...")
        
        top_10 = sorted(results, key=lambda x: x['score'], reverse=True)[:10]
        st.session_state.toplist_results = top_10
        my_bar.empty()
        st.success("Skanning klar!")

    if st.session_state.toplist_results:
        st.markdown(f"### 🔥 Topp 10: {theme_choice}")
        
        watchlist = load_watchlist()
        
        for rank, data in enumerate(st.session_state.toplist_results, 1):
            ticker = data['ticker']
            score = data['score']
            name = data['info'].get('shortName', ticker)
            color = "green" if score >= 75 else "orange" if score >= 50 else "red"
            
            with st.container():
                st.markdown(f"#### #{rank} | {name} ({ticker})")
                col1, col2, col3 = st.columns([2, 4, 2])
                with col1:
                    st.markdown(f"<h2 style='color: {color}; margin-top:0;'>{score}/100</h2>", unsafe_allow_html=True)
                with col2:
                    st.write(f"**P/E:** {round(data['pe'], 1) if data['pe'] else '-'} | **RSI:** {round(data['rsi'], 0) if data['rsi'] else '-'}")
                    trend_val = (data['ma50'] - data['ma200']) if (data['ma50'] and data['ma200']) else None
                    st.write(f"**Trend:** {get_label(trend_val, 'trend').replace('(', '').replace(')', '')}")
                with col3:
                    if ticker not in watchlist:
                        if st.button("⭐ Lägg till", key=f"top_{ticker}"):
                            watchlist[ticker] = {"shares": 0.0, "avg_price": 0.0}
                            save_watchlist(watchlist)
                            st.success("Tillagd!")
                            st.rerun()
                    else:
                        st.markdown("⭐ *I portfölj*")
                st.markdown("---")
