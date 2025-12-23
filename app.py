import streamlit as st
import pandas as pd
from pathlib import Path
import unicodedata
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analista Pro (Modo Debug)", layout="wide", page_icon="🐞")

# --- DEBUGGER (CHIVATO) ---
st.sidebar.title("🔧 ZONA DE DIAGNÓSTICO")

# 1. Encontrar la carpeta
data_dir = None
if Path("DATOS").exists(): data_dir = Path("DATOS")
elif Path("datos").exists(): data_dir = Path("datos")

if data_dir is None:
    st.sidebar.error("❌ NO EXISTE LA CARPETA 'datos' NI 'DATOS'.")
    st.sidebar.write("Carpetas actuales:", os.listdir('.'))
else:
    st.sidebar.success(f"✅ Carpeta encontrada: {data_dir}")
    
    # 2. Listar archivos dentro
    files = list(data_dir.glob("*"))
    st.sidebar.write("📂 Archivos detectados:")
    for f in files:
        st.sidebar.code(f.name)
        
    # 3. Intentar leer JUGADORES
    p_path = data_dir / "jugadores_raw.csv"
    if p_path.exists():
        try:
            df_check = pd.read_csv(p_path)
            st.sidebar.success(f"✅ CSV leído: {len(df_check)} filas")
            if not df_check.empty:
                st.sidebar.write("Columnas:", list(df_check.columns))
                if 'date' in df_check.columns:
                    st.sidebar.write("Fechas:", df_check['date'].head(3))
        except Exception as e:
            st.sidebar.error(f"❌ Error leyendo CSV: {e}")
    else:
        st.sidebar.error("❌ FALTA 'jugadores_raw.csv'")
        st.sidebar.warning("¿Quizás se llama 'jugadores_row.csv' o algo así?")

# --- DICCIONARIOS Y MAPEOS ---
TEAM_MAPPING = {
    "Alaves": "Alavés", "Ath Bilbao": "Athletic Club", "Ath Madrid": "Atlético Madrid",
    "Atletico Madrid": "Atlético Madrid", "Barcelona": "Barcelona", "Betis": "Real Betis",
    "Cadiz": "Cádiz", "Celta": "Celta Vigo", "Espanol": "Espanyol", "Getafe": "Getafe",
    "Girona": "Girona", "Granada": "Granada", "Las Palmas": "Las Palmas",
    "Mallorca": "Mallorca", "Osasuna": "Osasuna", "Rayo Vallecano": "Rayo Vallecano",
    "Real Madrid": "Real Madrid", "Real Sociedad": "Real Sociedad", "Sevilla": "Sevilla",
    "Valencia": "Valencia", "Valladolid": "Real Valladolid", "Villarreal": "Villarreal",
    "Almeria": "Almería", "Leganes": "Leganés"
}

PLAYER_DICT = {
    "player": "Jugador", "team": "Equipo", "date": "Fecha", "sh": "Remates",
    "sot": "A Puerta", "fls": "Faltas", "crdy": "T. Amarillas", "gls": "Goles",
    "ast": "Asistencias", "min": "Minutos", "game_count": "PJ"
}

# --- CARGA DE DATOS ---
@st.cache_data
def load_all_matches():
    if data_dir is None: return pd.DataFrame()
    files = list(data_dir.glob("*.csv"))
    files = [f for f in files if "jugadores" not in f.name]
    if not files: return pd.DataFrame()
    dfs = []
    for f in files:
        try:
            d = pd.read_csv(f, encoding='latin1')
            d.columns = [c.strip() for c in d.columns]
            if 'Date' in d.columns: d['Date'] = pd.to_datetime(d['Date'], dayfirst=True, errors='coerce')
            for col in ['HS','AS','HST','AST','HC','AC','HF','AF','HY','AY']:
                if col not in d.columns: d[col] = 0
            dfs.append(d)
        except: continue
    if not dfs: return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True).sort_values('Date', ascending=True)

@st.cache_data
def load_players():
    if data_dir is None: return pd.DataFrame()
    path = data_dir / "jugadores_raw.csv"
    if not path.exists(): return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        df.columns = [str(c).lower().strip() for c in df.columns]
        if 'squad' in df.columns: df = df.rename(columns={'squad': 'team'})
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce') # AÑADIDO dayfirst
            # FILTRO COMENTADO PARA PROBAR SI ES EL PROBLEMA
            # df = df[df['date'] > '2025-08-01'] 
        return df
    except: return pd.DataFrame()

# --- LÓGICA ---
def get_advanced_form(df, team, games=5, filter_mode='Auto'):
    if df.empty: return None
    df_curr = df[df['Date'] > '2025-08-01']
    if filter_mode == 'Home': matches = df_curr[df_curr['HomeTeam'] == team]
    elif filter_mode == 'Away': matches = df_curr[df_curr['AwayTeam'] == team]
    else: matches = df_curr[(df_curr['HomeTeam'] == team) | (df_curr['AwayTeam'] == team)]
    matches = matches.sort_values('Date', ascending=True).tail(games)
    if matches.empty: return None
    stats = {'goals_for': [], 'goals_against': [], 'shots': [], 'corners': [], 'cards': [], 'fouls': [], 'results': []}
    log = []
    for _, r in matches.iterrows():
        is_home = (r['HomeTeam'] == team)
        opp = r['AwayTeam'] if is_home else r['HomeTeam']
        d_str = r['Date'].strftime("%d/%m")
        if is_home:
            gf, ga = r['FTHG'], r['FTAG']; sh, co, ca, fo = r['HS'], r['HC'], r['HY'], r['HF']; tag = "(C)"
        else:
            gf, ga = r['FTAG'], r['FTHG']; sh, co, ca, fo = r['AS'], r['AC'], r['AY'], r['AF']; tag = "(F)"
        res = '✅' if gf > ga else ('❌' if gf < ga else '➖')
        stats['goals_for'].append(gf); stats['goals_against'].append(ga); stats['shots'].append(sh); stats['corners'].append(co); stats['cards'].append(ca); stats['fouls'].append(fo); stats['results'].append(res)
        log.append(f"{d_str} {res} {int(gf)}-{int(ga)} vs {opp} {tag}")
    count = len(matches)
    return {'gf': sum(stats['goals_for'])/count, 'ga': sum(stats['goals_against'])/count, 'sh': sum(stats['shots'])/count, 'corn': sum(stats['corners'])/count, 'card': sum(stats['cards'])/count, 'foul': sum(stats['fouls'])/count, 'log': log, 'raw_results': stats['results']}

def normalize_str(s):
    if not isinstance(s, str): return str(s)
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')

def fuzzy_match_team(team_name, df_players):
    if df_players.empty or 'team' not in df_players.columns: return None
    if team_name in TEAM_MAPPING: target = normalize_str(TEAM_MAPPING[team_name])
    else: target = normalize_str(team_name)
    player_teams = df_players['team'].dropna().unique()
    for t in player_teams:
        if normalize_str(t) == target: return t
    for t in player_teams:
        norm = normalize_str(t)
        if target in norm or norm in target: return t
    return None

def get_player_rankings(df_players, team_name):
    real_team = fuzzy_match_team(team_name, df_players)
    if not real_team: return None, None, None
    df_p = df_players[df_players['team'] == real_team].copy()
    if df_p.empty: return None, None, None
    scorers = df_p.groupby('player')[['gls', 'ast', 'min']].sum().sort_values('gls', ascending=False).head(5)
    shooters = df_p.groupby('player')[['sh', 'sot']].mean().sort_values('sh', ascending=False).head(5)
    bad_boys = df_p.groupby('player')[['fls', 'crdy']].mean().sort_values('fls', ascending=False).head(5)
    return scorers, shooters, bad_boys

def get_h2h_history(df_history, team1, team2):
    mask = ((df_history['HomeTeam'] == team1) & (df_history['AwayTeam'] == team2)) | ((df_history['HomeTeam'] == team2) & (df_history['AwayTeam'] == team1))
    h2h = df_history[mask].sort_values('Date', ascending=False)
    if h2h.empty: return None
    display_data = []
    for _, r in h2h.iterrows():
        try:
            display_data.append({"Fecha": r['Date'].strftime("%d/%m/%Y"), "Local": r['HomeTeam'], "Res": f"{int(r['FTHG'])}-{int(r['FTAG'])}", "Visitante": r['AwayTeam'], "1": r.get('B365H', '-'), "X": r.get('B365D', '-'), "2": r.get('B365A', '-')})
        except: continue
    return pd.DataFrame(display_data)

# --- INTERFAZ ---
full_df = load_all_matches()
df_players = load_players()
st.markdown("""<style>.win { color: #4CAF50; font-weight: bold; }.loss { color: #F44336; font-weight: bold; }.draw { color: #FFC107; font-weight: bold; }</style>""", unsafe_allow_html=True)

if full_df.empty:
    st.error("⚠️ Carpeta DATOS vacía o sin CSVs de partidos.")
else:
    all_teams = sorted(full_df[full_df['Date'] > '2025-08-01']['HomeTeam'].unique())
    if not all_teams: all_teams = sorted(full_df['HomeTeam'].unique())
    tabs = st.tabs(["🆚 Comparador PRO", "🛡️ Equipos", "⚽ Jugadores", "🏟️ Plantillas"])

    with tabs[0]:
        c1, c2, c3 = st.columns([2, 2, 1])
        local = c1.selectbox("Local", all_teams, index=0)
        visitante = c2.selectbox("Visitante", all_teams, index=1)
        with c3: n_games = st.selectbox("Partidos", [5, 10, 20], index=0)
        st.divider()
        stats_loc = get_advanced_form(full_df, local, n_games, "Home")
        stats_vis = get_advanced_form(full_df, visitante, n_games, "Away")
        
        if stats_loc and stats_vis:
            st.subheader(f"📊 Estadísticas ({local} Casa vs {visitante} Fuera)")
            c_r1, c_r2 = st.columns(2)
            with c_r1: st.markdown(f"**Racha {local}:** {' '.join([f'<span class={(x=='✅' and 'win') or (x=='❌' and 'loss') or 'draw'}>{x}</span>' for x in stats_loc['raw_results']])}", unsafe_allow_html=True)
            with c_r2: st.markdown(f"**Racha {visitante}:** {' '.join([f'<span class={(x=='✅' and 'win') or (x=='❌' and 'loss') or 'draw'}>{x}</span>' for x in stats_vis['raw_results']])}", unsafe_allow_html=True)
            comp_data = {"Métrica": ["Goles A/C", "Tiros Tot/Puer", "Córners", "Tarjetas", "Faltas"], f"{local}": [f"{stats_loc['gf']:.1f} / {stats_loc['ga']:.1f}", f"{stats_loc['sh']:.1f} / {stats_loc['sot']:.1f}", f"{stats_loc['corn']:.1f}", f"{stats_loc['card']:.1f}", f"{stats_loc['foul']:.1f}"], f"{visitante}": [f"{stats_vis['gf']:.1f} / {stats_vis['ga']:.1f}", f"{stats_vis['sh']:.1f} / {stats_vis['sot']:.1f}", f"{stats_vis['corn']:.1f}", f"{stats_vis['card']:.1f}", f"{stats_vis['foul']:.1f}"]}
            st.dataframe(pd.DataFrame(comp_data), hide_index=True, use_container_width=True)
        
        st.divider()
        st.subheader("🔥 Top Jugadores (Media)")
        scorers_L, shooters_L, cards_L = get_player_rankings(df_players, local)
        scorers_V, shooters_V, cards_V = get_player_rankings(df_players, visitante)
        col_p_local, col_p_visit = st.columns(2)
        with col_p_local:
            st.markdown(f"### 🏠 {local}")
            if scorers_L is not None:
                st.caption("⚽ Goleadores"); st.dataframe(scorers_L.rename(columns={'gls':'G','ast':'A'}), use_container_width=True)
                st.caption("🎯 Tiros"); st.dataframe(shooters_L.rename(columns={'sh':'T','sot':'P'}).style.format("{:.1f}"), use_container_width=True)
            else: st.info(f"Sin datos jugadores (Debug: {fuzzy_match_team(local, df_players)})")
        with col_p_visit:
            st.markdown(f"### ✈️ {visitante}")
            if scorers_V is not None:
                st.caption("⚽ Goleadores"); st.dataframe(scorers_V.rename(columns={'gls':'G','ast':'A'}), use_container_width=True)
                st.caption("🎯 Tiros"); st.dataframe(shooters_V.rename(columns={'sh':'T','sot':'P'}).style.format("{:.1f}"), use_container_width=True)
            else: st.info(f"Sin datos jugadores (Debug: {fuzzy_match_team(visitante, df_players)})")
        
        st.divider()
        h2h_df = get_h2h_history(full_df, local, visitante)
        with st.expander("📚 Historial H2H (2004-2026)"):
            if h2h_df is not None: st.dataframe(h2h_df, hide_index=True, use_container_width=True)
            else: st.write("No hay datos.")

    # Resto de pestañas simplificadas para brevedad (el problema está arriba)
    with tabs[1]:
        tm = st.selectbox("Equipo", all_teams, key="tab2"); st.write(get_advanced_form(full_df, tm, 38, 'General'))
    with tabs[2]:
        if not df_players.empty:
             st.dataframe(df_players.head())
