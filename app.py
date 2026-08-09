import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
import altair as alt

# --- Databas för Sparlistan ---
DB_FILE = "watchlist.json"

def load_watchlist():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return list(data.keys())
                return data
            except:
                return []
    return []

def save_watchlist(watchlist):
    with open(DB_FILE, "w") as f:
        json.dump(watchlist, f)

# --- Ticker-listor för Top-listan ---
STHLM_TICKERS = [
    "VOLV-B.ST", "INVE-B.ST", "ATCO-A.ST", "HM-B.ST", "SEB-A.ST", 
    "SHB-A.ST", "SWED-A.ST", "ERIC-B.ST", "ASSA-B.ST", "EVO.ST", 
    "HEXA-B.ST", "SAND.ST", "NIBE-B.ST", "SCA-B.ST", "TELIA.ST", 
    "ALFA.ST", "SKF-B.ST", "BOL.ST", "GETI-B.ST", "SINCH.ST",
    "KINV-B.ST", "LATB.ST", "EPI-A.ST", "INDU-C.ST", "SAAB-B.ST"
]

NASDAQ_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", 
    "NFLX", "ADBE", "AMD", "INTC", "CSCO", "PEP", "AVGO", 
    "TXN", "QCOM", "COST", "AMGN", "INTU", "SBUX", "PYPL",
    "AMAT", "MU", "CRWD", "PANW"
]

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

# --- Smarta etiketter (Bra, Medel, Dålig) ---
def get_label(value, metric_type):
    if value is None or pd.isna(value):
        return "(Saknas)"
    
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

# --- Smart insiktsgenerator ---
def generate_insights(pe, peg, div, rsi, ma50, ma200, beta):
    positives = []
    risks = []
    
    if pe is not None and not pd.isna(pe) and pe > 0:
        if pe < 15: positives.append("Låg värdering (P/E under 15).")
        elif pe > 30: risks.append("Mycket hög värdering (P/E över 30).")
        
    if peg is not None and not pd.isna(peg) and peg > 0:
        if peg < 1.0: positives.append("Bolaget växer snabbt mot prislappen (PEG under 1.0).")
        elif peg > 2.0: risks.append("Tillväxttakten motiverar kanske inte prislappen (PEG över 2.0).")
        
    if div is not None and not pd.isna(div) and div > 0.03:
        positives.append(f"Hög direktavkastning ({round(div*100,1)}%).")
    elif div is None or pd.isna(div) or div == 0:
        risks.append("Ger ingen utdelning.")
        
    if ma50 is not None and ma200 is not None and not pd.isna(ma50) and not pd.isna(ma200):
        if ma50 > ma200: positives.append("Teknisk styrka: Långsiktig uppåttrend (Golden Cross).")
        else: risks.append("Teknisk svaghet: Långsiktig nedåttrend.")
        
    if rsi is not None and not pd.isna(rsi):
        if rsi < 30: positives.append("Kortsiktigt översåld. Kan finnas köpläge.")
        elif rsi > 70: risks.append("Kortsiktigt överköpt. Risk för tillfällig rekyl.")
        
    if beta is not None and not pd.isna(beta) and beta > 1.3:
        risks.append("Hög volatilitet (Beta över 1.3). Svänger mer än börsen.")
        
    if not positives: positives.append("Hittar inga utmärkande styrkor.")
    if not risks: risks.append("Hittar inga uppenbara röda flaggor.")
        
    return positives, risks

# --- Algoritmen för poängberäkning ---
def calculate_score_100(pe, peg, dividend, recommendation, rsi, macd_diff, ma50, ma200):
    score = 0
    details = {}

    if pe is not None and not pd.isna(pe) and pe > 0:
        if pe < 15: score += 15; details['P/E'] = "15 p"
        elif 15 <= pe <= 25: score += 7; details['P/E'] = "7 p"
        else: details['P/E'] = "0 p"
    else: details['P/E'] = "0 p"

    if peg is not None and not pd.isna(peg) and peg > 0:
        if peg < 1.0: score += 15; details['PEG'] = "15 p"
        elif 1.0 <= peg <= 1.5: score += 7; details['PEG'] = "7 p"
        else: details['PEG'] = "0 p"
    else: details['PEG'] = "0 p"

    if recommendation and isinstance(recommendation, str):
        rec = recommendation.lower()
        if 'strong_buy' in rec: score += 20; details['Analytiker'] = "20 p"
        elif 'buy' in rec: score += 15; details['Analytiker'] = "15 p"
        elif 'hold' in rec: score += 5; details['Analytiker'] = "5 p"
        else: details['Analytiker'] = "0 p"
    else: details['Analytiker'] = "0 p"

    if macd_diff is not None and not pd.isna(macd_diff):
        if macd_diff > 0: score += 15; details['MACD'] = "15 p"
        else: details['MACD'] = "0 p"
    else: details['MACD'] = "0 p"

    if ma50 is not None and ma200 is not None and not pd.isna(ma50) and not pd.isna(ma200):
        if ma50 > ma200: score += 15; details['Golden Cross'] = "15 p"
        else: details['Golden Cross'] = "0 p"
    else: details['Golden Cross'] = "0 p"

    if rsi is not None and not pd.isna(rsi):
        if rsi < 30: score += 10; details['RSI'] = "10 p"
        elif 30 <= rsi <= 70: score += 5; details['RSI'] = "5 p"
        else: details['RSI'] = "0 p"
    else: details['RSI'] = "0 p"
        
    if dividend is not None and not pd.isna(dividend) and dividend > 0:
        score += 10; details['Utdelning'] = "10 p"
    else: details['Utdelning'] = "0 p"

    return score, details

def safe_val(val):
    if pd.isna(val):
        return None
    return float(val)

# --- Historisk Tidsmaskin ---
def get_historical_scores(ticker_symbol, current_pe, current_peg, dividend, recommendation):
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="2y")
    
    if hist.empty or len(hist) < 200:
        return None
        
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
    
    try:
        monthly_data = hist.resample('ME').last().tail(12)
    except Exception:
        monthly_data = hist.resample('M').last().tail(12)
    
    current_price = safe_val(hist['Close'].iloc[-1])
    eps = current_price / current_pe if (current_price and current_pe and current_pe > 0) else None
    
    swe_months = {
        1: "Januari", 2: "Februari", 3: "Mars", 4: "April",
        5: "Maj", 6: "Juni", 7: "Juli", 8: "Augusti",
        9: "September", 10: "Oktober", 11: "November", 12: "December"
    }
    
    history_dict = {}
    
    for date, row in monthly_data.iterrows():
        close_price = safe_val(row['Close'])
        if not close_price:
            continue
            
        hist_pe = close_price / eps if eps else None
        hist_div = (dividend * current_price) / close_price if (dividend and current_price) else None
        hist_peg = current_peg * (hist_pe / current_pe) if (current_peg and current_pe and current_pe > 0 and hist_pe) else None

        s, _ = calculate_score_100(
            hist_pe, hist_peg, hist_div, recommendation, 
            safe_val(row['RSI']), safe_val(row['MACD_Diff']), 
            safe_val(row['MA50']), safe_val(row['MA200'])
        )
        
        month_str = f"{swe_months[date.month]} '{str(date.year)[-2:]}"
        history_dict[month_str] = s
        
    return history_dict

# --- Huvudfunktion för datainsamling ---
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
    
    # Hämta nyheter
    try:
        news = ticker.news[:3]
    except Exception:
        news = []
    
    hist_5y_data = ticker.history(period="5y")
    if not hist_5y_data.empty and 'Close' in hist_5y_data.columns:
        hist_5y = hist_5y_data['Close']
    else:
        hist_5y = pd.Series()
    
    hist_1y = ticker.history(period="1y") 
    rsi = macd_diff = ma50 = ma200 = None
    if not hist_1y.empty and len(hist_1y) >= 200:
        delta = hist_1y['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = safe_val((100 - (100 / (1 + rs))).iloc[-1])
        
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
        'info': info, 'score': score, 'breakdown': breakdown, 
        'pe': pe, 'peg': peg, 'div': div, 'rsi': rsi, 'ma50': ma50, 'ma200': ma200,
        'positives': positives, 'risks': risks,
        'hist_5y': hist_5y, 'historical_scores': historical_scores,
        'ticker': ticker_symbol, 'news': news
    }

# --- Streamlit Gränssnitt ---
st.set_page_config(page_title="Aktierankaren Pro", page_icon="📈", layout="centered")

if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = None
if 'stock_data' not in st.session_state:
    st.session_state.stock_data = None
if 'watchlist_data' not in st.session_state:
    st.session_state.watchlist_data = {}
if 'search_options' not in st.session_state:
    st.session_state.search_options = []
# Minne för Toplistan
if 'toplist_results' not in st.session_state:
    st.session_state.toplist_results = []

# Tre flikar
tab1, tab2, tab3 = st.tabs(["🔍 Sök & Analysera", "⭐ Min Sparlista", "🏆 Top listan"])

# --- FLIK 1: Sök & Analysera ---
with tab1:
    st.title("📈 Aktierankaren")
    st.write("Sök på ett företagsnamn (t.ex. Google eller Investor).")

    with st.form("search_form"):
        name_query = st.text_input("1. Sök företagsnamn eller ticker:", "")
        search_submitted = st.form_submit_button("Sök i registret")
        
        if search_submitted and name_query:
            with st.spinner("Letar upp aktien..."):
                st.session_state.search_options = search_ticker_by_name(name_query)

    if st.session_state.search_options:
        selected_option = st.selectbox("2. Välj rätt aktie från listan:", st.session_state.search_options)
        ticker_to_analyze = selected_option.split(" - ")[0]
        
        if st.button("Hämta Ranking", type="primary"):
            with st.spinner(f"Analyserar {ticker_to_analyze}..."):
                st.session_state.current_ticker = ticker_to_analyze
                data = fetch_stock_data(ticker_to_analyze)
                if data:
                    st.session_state.stock_data = data
                else:
                    st.error("Kunde tyvärr inte hämta data för denna aktie just nu.")
                    st.session_state.stock_data = None

    if st.session_state.current_ticker and st.session_state.stock_data:
        data = st.session_state.stock_data
        ticker = st.session_state.current_ticker
        
        st.markdown("---")
        st.header(data['info'].get('shortName', ticker))
        
        watchlist = load_watchlist()
        if ticker not in watchlist:
            if st.button("⭐ Spara till Watchlist", key="save_btn_search"):
                watchlist.append(ticker)
                save_watchlist(watchlist)
                st.success(f"{ticker} sparades i din lista!")
                st.rerun()
        else:
            st.info("⭐ Sparad i din Watchlist")

        score = data['score']
        color = "green" if score >= 75 else "orange" if score >= 50 else "red"
        st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 80px;'>{score} / 100</h1>", unsafe_allow_html=True)

        st.markdown("### 💡 Insikter om aktien")
        col_pos, col_neg = st.columns(2)
        with col_pos:
            st.success("**Möjligheter:**\n" + "\n".join([f"- {p}" for p in data['positives']]))
        with col_neg:
            st.error("**Risker:**\n" + "\n".join([f"- {r}" for r in data['risks']]))

        # NYHETER OCH VARNINGSKLOCKOR
        st.markdown("### 📰 Nyheter & Varningsklockor")
        if data['news']:
            for n in data['news']:
                title = n.get('title', 'Nyhet')
                link = n.get('link', '#')
                publisher = n.get('publisher', 'Nyhetskälla')
                st.markdown(f"- [{title}]({link}) *(Källa: {publisher})*")
        else:
            st.write("Hittade inga aktuella nyheter för tillfället.")

        st.markdown("### 📊 Uppdelning av data")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Faktorer")
            st.write(f"**P/E:** {round(data['pe'], 2) if data['pe'] else '-'} {get_label(data['pe'], 'pe')}")
            st.write(f"**PEG:** {round(data['peg'], 2) if data['peg'] else '-'} {get_label(data['peg'], 'peg')}")
            st.write(f"**Utdelning:** {round(data['div'] * 100, 2) if data['div'] else 0}% {get_label(data['div'], 'div')}")
            st.write(f"**RSI (14):** {round(data['rsi'], 0) if data['rsi'] else '-'} {get_label(data['rsi'], 'rsi')}")
            
            trend_val = (data['ma50'] - data['ma200']) if (data['ma50'] and data['ma200']) else None
            st.write(f"**Trend (MA50 vs MA200):** {get_label(trend_val, 'trend')}")

        with col2:
            st.subheader("Poäng (Totalt)")
            for k, v in data['breakdown'].items():
                st.write(f"**{k}:** {v}")

        st.markdown("---")
        st.markdown("### 📅 Poänghistorik (Senaste 12 månaderna)")
        if data['historical_scores']:
            hist_df = pd.DataFrame({
                'Månad': list(data['historical_scores'].keys()),
                'Poäng': list(data['historical_scores'].values())
            })
            
            bar_chart = alt.Chart(hist_df).mark_bar(color='#2ecc71').encode(
                x=alt.X('Månad', sort=None, title=''),
                y=alt.Y('Poäng', title='Poäng', scale=alt.Scale(domain=[0, 100])),
                tooltip=['Månad', 'Poäng']
            )
            st.altair_chart(bar_chart, use_container_width=True)

        st.markdown("### 📈 Kursutveckling (Senaste 5 åren)")
        if not data['hist_5y'].empty:
            df_5y = data['hist_5y'].reset_index()
            df_5y.columns = ['Datum', 'Pris']
            
            line_chart = alt.Chart(df_5y).mark_line(color='#3498db').encode(
                x=alt.X('Datum', title=''),
                y=alt.Y('Pris', title='Aktiekurs', scale=alt.Scale(zero=False)),
                tooltip=['Datum', 'Pris']
            )
            st.altair_chart(line_chart, use_container_width=True)

# --- FLIK 2: Min Sparlista ---
with tab2:
    st.title("⭐ Min Sparlista")
    
    watchlist = load_watchlist()
    
    if len(watchlist) == 0:
        st.write("Din sparlista är tom.")
    else:
        if st.button("🔄 Uppdatera alla poäng", key="update_all"):
            for ticker_symbol in watchlist:
                with st.spinner(f"Hämtar data för {ticker_symbol}..."):
                    data = fetch_stock_data(ticker_symbol)
                    if data:
                        st.session_state.watchlist_data[ticker_symbol] = data

        st.markdown("---")
        
        for ticker in watchlist:
            col_name, col_score, col_del = st.columns([5, 3, 1])
            data = st.session_state.watchlist_data.get(ticker)
            
            with col_name:
                if data:
                    st.markdown(f"**{ticker}** - {data['info'].get('shortName', '')}")
                else:
                    st.markdown(f"**{ticker}**")
                    
            with col_score:
                if data:
                    score = data['score']
                    color = "green" if score >= 75 else "orange" if score >= 50 else "red"
                    st.markdown(f"<span style='color:{color}; font-weight:bold; font-size:18px;'>{score} / 100</span>", unsafe_allow_html=True)
                else:
                    st.markdown("*(Inte uppdaterad)*")
                    
            with col_del:
                if st.button("❌", key=f"del_{ticker}"):
                    watchlist.remove(ticker)
                    save_watchlist(watchlist)
                    if ticker in st.session_state.watchlist_data:
                        del st.session_state.watchlist_data[ticker]
                    st.rerun()
            
            if data:
                with st.expander("Visa insikter"):
                    col_pos, col_neg = st.columns(2)
                    with col_pos:
                        st.success("\n".join([f"- {p}" for p in data['positives']]))
                    with col_neg:
                        st.error("\n".join([f"- {r}" for r in data['risks']]))
                        
                    st.write(f"**Snabbfakta:** P/E: {round(data['pe'], 2) if data['pe'] else '-'} | PEG: {round(data['peg'], 2) if data['peg'] else '-'} | Utdelning: {round(data['div'] * 100, 2) if data['div'] else 0}% | RSI: {round(data['rsi'], 0) if data['rsi'] else '-'}")
            st.markdown("---")

# --- FLIK 3: Top Listan ---
with tab3:
    st.title("🏆 Top listan (Vinnarna just nu)")
    st.write("Skanna marknaden för att hitta aktierna med högst algoritmpoäng. Appen letar bland de mest omsatta bolagen på vald börs.")
    
    exchange_choice = st.selectbox("Vilken marknad vill du scanna?", ["Stockholmsbörsen (Top 25)", "Nasdaq US (Top 25 Tech)"])
    
    if st.button("🔍 Scanna Marknaden (Tar ca 10 sekunder)", type="primary"):
        tickers_to_scan = STHLM_TICKERS if "Stockholm" in exchange_choice else NASDAQ_TICKERS
        
        progress_text = "Skannar bolagen, ett ögonblick..."
        my_bar = st.progress(0, text=progress_text)
        
        results = []
        for i, ticker in enumerate(tickers_to_scan):
            data = fetch_stock_data(ticker)
            if data:
                results.append(data)
            my_bar.progress((i + 1) / len(tickers_to_scan), text=f"Analyserar {ticker} ({i+1}/{len(tickers_to_scan)})...")
        
        top_10 = sorted(results, key=lambda x: x['score'], reverse=True)[:10]
        st.session_state.toplist_results = top_10
        
        my_bar.empty()
        st.success("Skanning klar! Här är top 10:")

    if st.session_state.toplist_results:
        st.markdown(f"### 🔥 Topp 10: {exchange_choice}")
        
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
                        if st.button("⭐ Spara", key=f"top_{ticker}"):
                            watchlist.append(ticker)
                            save_watchlist(watchlist)
                            st.success("Sparad!")
                            st.rerun()
                    else:
                        st.markdown("⭐ *Sparad*")
                        
                st.markdown("---")
