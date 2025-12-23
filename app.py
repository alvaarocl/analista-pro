import streamlit as st
import pandas as pd
from pathlib import Path
import unicodedata
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analista Pro Total", layout="wide", page_icon="⚽")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .win { color: #4CAF50; font-weight: bold; font-size: 1.2em; }
    .loss { color: #F44336; font-weight: bold; font-size: 1.2em; }
    .draw { color: #FFC107; font-weight: bold; font-size: 1.2em; }
    .stat-box { background-color: #262730; padding: 10px; border-radius: 5px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- DIAGNÓSTICO EN SIDEBAR ---
st.sidebar.title("🔧 Estado del Sistema")

# 1. Buscar la carpeta de datos
data_dir = None
if Path("DATOS").exists(): data_dir = Path("DATOS")
elif Path("datos").exists(): data_dir = Path("datos")

if data_dir is None:
    st.sidebar.error("❌ NO SE ENCUENTRA LA CARPETA 'datos' NI 'DATOS'.")
else:
    st.sidebar.success(f"✅ Carpeta encontrada: {data_dir}")
    p_path = data_dir / "jugadores_raw.csv"
    if p_path.exists():
        st.sidebar.success("✅ jugadores_raw.csv detectado")
    else:
        st.sidebar.error("❌ FALTA 'jugadores_raw.csv'")

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

# --- FUNCIONES DE CARGA ---
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
            
            if 'Date' in d.columns:
                d['Date'] = pd.to_datetime(d['Date'], dayfirst=True, errors='coerce')
            
            # Asegurar columnas
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
        # Normalizar columnas a minúsculas
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # Corrección nombre equipo
        if 'squad' in df.columns: df = df.rename(columns={'squad': 'team'})
        
        # Corrección fechas
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            
        return df
    except: return pd.DataFrame()

# --- FUNCIONES LÓGICAS ---
def get_advanced_form(df, team, games=5, filter_mode='Auto'):
    if df.empty: return None
    
    # Filtro de temporada (Partidos)
    df_curr = df.sort_values('Date', ascending=True) 
    
    if filter_mode == 'Home': matches = df_curr[df_curr['HomeTeam'] == team]
    elif filter_mode == 'Away': matches = df_curr[df_curr['AwayTeam'] == team]
    else: matches = df_curr[(df_curr['HomeTeam'] == team) | (df_curr['AwayTeam'] == team)]
    
    matches = matches.sort_values('Date', ascending=True).tail(games)
    
    if matches.empty: return None
    
    stats = {'goals_for': [], 'goals_against': [], 'shots': [], 'shots_target': [], 
             'corners': [], 'cards': [], 'fouls': [], 'results': []}
    log = []

    for _, r in matches.iterrows():
        is_home = (r['HomeTeam'] == team)
        opp = r['AwayTeam'] if is_home else r['HomeTeam']
        d_str = r['Date'].strftime("%d/%m")
        
        if is_home:
            gf, ga = r['FTHG'], r['FTAG']; sh, sot = r['HS'], r['HST']
            co, ca, fo = r['HC'], r['HY'], r['HF']; tag = "(C)"
        else:
            gf, ga = r['FTAG'], r['FTHG']; sh, sot = r['AS'], r['AST']
            co, ca, fo = r['AC'], r['AY'], r['AF']; tag = "(F)"
            
        if gf > ga: res = '✅'
        elif gf == ga: res = '➖'
        else: res = '❌'
        
        stats['goals_for'].append(gf); stats['goals_against'].append(ga)
        stats['shots'].append(sh); stats['shots_target'].append(sot)
        stats['corners'].append(co); stats['cards'].append(ca); stats['fouls'].append(fo)
        stats['results'].append(res)
        log.append(f"{d_str} {res} {int(gf)}-{int(ga)} vs {opp} {tag}")

    count = len(matches)
    return {
        'gf': sum(stats['goals_for'])/count, 'ga': sum(stats['goals_against'])/count,
        'sh': sum(stats['shots'])/count, 'sot': sum(stats['shots_target'])/count,
        'corn': sum(stats['corners'])/count, 'card': sum(stats['cards'])/count, 
        'foul': sum(stats['fouls'])/count, 'log': log, 'raw_results': stats['results']
    }

def generate_streak_html(results):
    html = ""
    for r in results:
        if r == '✅': color = 'win'
        elif r == '❌': color = 'loss'
        else: color = 'draw'
        html += f"<span class='{color}'>{r}</span> "
    return html

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
    
    # Asegurar que las columnas son numéricas
    for col in ['gls', 'ast', 'min', 'sh', 'sot', 'fls', 'crdy']:
        if col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)

    scorers = df_p.groupby('player')[['gls', 'ast', 'min']].sum().sort_values('gls', ascending=False).head(5)
    
    shooters = df_p.groupby('player')[['sh', 'sot']].mean().sort_values('sh', ascending=False).head(5)
    bad_boys = df_p.groupby('player')[['fls', 'crdy']].mean().sort_values('fls', ascending=False).head(5)
    
    return scorers, shooters, bad_boys

def get_h2h_history(df_history, team1, team2):
    mask = ((df_history['HomeTeam'] == team1) & (df_history['AwayTeam'] == team2)) | \
           ((df_history['HomeTeam'] == team2) & (df_history['AwayTeam'] == team1))
    h2h = df_history[mask].sort_values('Date', ascending=False)
    if h2h.empty: return None
    display_data = []
    for _, r in h2h.iterrows():
        try:
            display_data.append({
                "Fecha": r['Date'].strftime("%d/%m/%Y"), "Local": r['HomeTeam'],
                "Res": f"{int(r['FTHG'])}-{int(r['FTAG'])}", "Visitante": r['AwayTeam'],
                "1": r.get('B365H', '-'), "X": r.get('B365D', '-'), "2": r.get('B365A', '-')
            })
        except: continue
    return pd.DataFrame(display_data)

# --- INTERFAZ PRINCIPAL ---
full_df = load_all_matches()
df_players = load_players()

if full_df.empty:
    st.error("⚠️ La base de datos de partidos está vacía. Revisa la barra lateral.")
else:
    # --- ARREGLO DEL ERROR DE SORTED ---
    # Cogemos los equipos del último año, filtramos nulos y convertimos a string para evitar errores de ordenación
    recent_matches = full_df.sort_values('Date').tail(400)
    unique_teams_raw = recent_matches['HomeTeam'].unique()
    # Limpieza: Solo strings y no nulos
    clean_teams = [str(t) for t in unique_teams_raw if pd.notna(t)]
    all_teams = sorted(clean_teams)
    
    # Fallback si falla lo anterior
    if not all_teams: 
        raw_all = full_df['HomeTeam'].unique()
        all_teams = sorted([str(t) for t in raw_all if pd.notna(t)])

    tabs = st.tabs(["🆚 Comparador PRO", "🛡️ Equipos", "⚽ Jugadores", "🏟️ Plantillas"])

    # ==============================================================================
    # TAB 1: COMPARADOR PRO
    # ==============================================================================
    with tabs[0]:
        c1, c2, c3 = st.columns([2, 2, 1])
        local = c1.selectbox("Local", all_teams, index=0)
        visitante = c2.selectbox("Visitante", all_teams, index=1)
        with c3: n_games = st.selectbox("Partidos", [5, 10, 20], index=0)
        
        st.divider()

        filter_loc = "Home"
        filter_vis = "Away"
        
        stats_loc = get_advanced_form(full_df, local, n_games, filter_loc)
        stats_vis = get_advanced_form(full_df, visitante, n_games, filter_vis)
        
        if stats_loc and stats_vis:
            st.subheader(f"📊 Estadísticas ({local} Casa vs {visitante} Fuera)")
            c_r1, c_r2 = st.columns(2)
            with c_r1: 
                html_racha = generate_streak_html(stats_loc['raw_results'])
                st.markdown(f"**Racha {local}:** {html_racha}", unsafe_allow_html=True)
            with c_r2:
                html_racha = generate_streak_html(stats_vis['raw_results'])
                st.markdown(f"**Racha {visitante}:** {html_racha}", unsafe_allow_html=True)

            comp_data = {
                "Métrica": ["Goles A/C", "Tiros Tot/Puer", "Córners", "Tarjetas", "Faltas"],
                f"{local}": [f"{stats_loc['gf']:.1f} / {stats_loc['ga']:.1f}", f"{stats_loc['sh']:.1f} / {stats_loc['sot']:.1f}", f"{stats_loc['corn']:.1f}", f"{stats_loc['card']:.1f}", f"{stats_loc['foul']:.1f}"],
                f"{visitante}": [f"{stats_vis['gf']:.1f} / {stats_vis['ga']:.1f}", f"{stats_vis['sh']:.1f} / {stats_vis['sot']:.1f}", f"{stats_vis['corn']:.1f}", f"{stats_vis['card']:.1f}", f"{stats_vis['foul']:.1f}"]
            }
            st.dataframe(pd.DataFrame(comp_data), hide_index=True, use_container_width=True)
        else:
            st.warning("Faltan datos de partidos recientes.")

        st.divider()

        # JUGADORES
        st.subheader("🔥 Top Jugadores (Media)")
        scorers_L, shooters_L, cards_L = get_player_rankings(df_players, local)
        scorers_V, shooters_V, cards_V = get_player_rankings(df_players, visitante)
        
        col_p_local, col_p_visit = st.columns(2)
        
        with col_p_local:
            st.markdown(f"### 🏠 {local}")
            if scorers_L is not None:
                st.caption("⚽ Goleadores"); st.dataframe(scorers_L.rename(columns={'gls':'G','ast':'A'}), use_container_width=True)
                st.caption("🎯 Tiros"); st.dataframe(shooters_L.rename(columns={'sh':'T','sot':'P'}).style.format("{:.1f}"), use_container_width=True)
            else: 
                st.info(f"Sin datos jugadores.")
                if not df_players.empty:
                    st.caption(f"DEBUG: Buscando '{local}' o mapeado '{TEAM_MAPPING.get(local)}'")

        with col_p_visit:
            st.markdown(f"### ✈️ {visitante}")
            if scorers_V is not None:
                st.caption("⚽ Goleadores"); st.dataframe(scorers_V.rename(columns={'gls':'G','ast':'A'}), use_container_width=True)
                st.caption("🎯 Tiros"); st.dataframe(shooters_V.rename(columns={'sh':'T','sot':'P'}).style.format("{:.1f}"), use_container_width=True)
            else: st.info(f"Sin datos jugadores.")

        st.divider()
        h2h_df = get_h2h_history(full_df, local, visitante)
        with st.expander("📚 Ver Historial H2H (2004-2026)", expanded=False):
            if h2h_df is not None: st.dataframe(h2h_df, hide_index=True, use_container_width=True)
            else: st.write("No hay datos previos.")

    # ==============================================================================
    # TAB 3: JUGADORES
    # ==============================================================================
    with tabs[2]:
        st.header("🔎 Buscador")
        with st.expander("🕵️ Ver Datos Crudos (Debug)", expanded=False):
            st.write(f"Filas totales cargadas: {len(df_players)}")
            st.write(df_players.head())
            
        if not df_players.empty:
            c1, c2 = st.columns(2)
            team_sel = c1.selectbox("Equipo", all_teams, key="tab3_tm")
            real_team_name = fuzzy_match_team(team_sel, df_players)
            
            if real_team_name:
                players_list = sorted(df_players[df_players['team'] == real_team_name]['player'].unique())
                pl_sel = c2.selectbox("Jugador", players_list)
                p_stats = df_players[df_players['player'] == pl_sel].sort_values('date', ascending=False)
                st.write(f"**Stats de {pl_sel}:**")
                st.dataframe(p_stats[['date','game','min','gls','ast','sh','sot','fls','crdy']], hide_index=True, use_container_width=True)
            else:
                st.warning(f"No encuentro jugadores para {team_sel}.")
        else:
            st.error("El DataFrame de jugadores está vacío. Revisa la carga.")
    
    # Resto de pestañas...
    with tabs[1]:
        tm = st.selectbox("Equipo", all_teams, key="tab2"); st.write(get_advanced_form(full_df, tm, 38, 'General'))
    with tabs[3]:
        st.header("📊 Plantilla")
        if not df_players.empty:
            team_sq = st.selectbox("Equipo", all_teams, key="tab4_tm")
            real_team_sq = fuzzy_match_team(team_sq, df_players)
            if real_team_sq:
                df_sq = df_players[df_players['team'] == real_team_sq]
                summ = df_sq.groupby('player').agg({'min':'sum', 'gls':'sum', 'ast':'sum', 'sh':'mean', 'sot':'mean', 'fls':'mean', 'crdy':'sum'}).reset_index()
                st.dataframe(summ.rename(columns={'min':'Min','gls':'G','ast':'A','sh':'Tiros/P','sot':'Puerta/P','fls':'Faltas/P','crdy':'Amarillas'}).style.format("{:.2f}", subset=['Tiros/P','Puerta/P','Faltas/P']), hide_index=True, use_container_width=True, height=700)
