import streamlit as st
import pandas as pd
from pathlib import Path
import unicodedata

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analista Pro Total", layout="wide", page_icon="⚽")

# --- DICCIONARIOS Y MAPEOS ---
# Esto es CRÍTICO: Traduce los nombres de football-data a los de FBref (jugadores)
TEAM_MAPPING = {
    "Alaves": "Alavés",
    "Ath Bilbao": "Athletic Club",
    "Ath Madrid": "Atlético Madrid",
    "Atletico Madrid": "Atlético Madrid",
    "Barcelona": "Barcelona",
    "Betis": "Real Betis",
    "Cadiz": "Cádiz",
    "Celta": "Celta Vigo",
    "Espanol": "Espanyol",
    "Getafe": "Getafe",
    "Girona": "Girona",
    "Granada": "Granada",
    "Las Palmas": "Las Palmas",
    "Mallorca": "Mallorca",
    "Osasuna": "Osasuna",
    "Rayo Vallecano": "Rayo Vallecano",
    "Real Madrid": "Real Madrid",
    "Real Sociedad": "Real Sociedad",
    "Sevilla": "Sevilla",
    "Valencia": "Valencia",
    "Valladolid": "Real Valladolid",
    "Villarreal": "Villarreal",
    "Almeria": "Almería",
    "Leganes": "Leganés"
}

PLAYER_DICT = {
    "player": "Jugador", "team": "Equipo", "date": "Fecha",
    "sh": "Remates", "sot": "A Puerta", "fls": "Faltas", 
    "crdy": "T. Amarillas", "gls": "Goles", "ast": "Asistencias",
    "min": "Minutos", "game_count": "PJ"
}

# --- FUNCIÓN INTELIGENTE PARA ENCONTRAR DATOS ---
def get_data_dir():
    if Path("DATOS").exists(): return Path("DATOS")
    elif Path("datos").exists(): return Path("datos")
    return None

# --- CARGA DE DATOS ---
@st.cache_data
def load_all_matches():
    data_dir = get_data_dir()
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
            
            # Asegurar columnas estadísticas
            for col in ['HS','AS','HST','AST','HC','AC','HF','AF','HY','AY']:
                if col not in d.columns: d[col] = 0
                
            dfs.append(d)
        except: continue
        
    if not dfs: return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True).sort_values('Date', ascending=True)

@st.cache_data
def load_players():
    data_dir = get_data_dir()
    if data_dir is None: return pd.DataFrame()
    path = data_dir / "jugadores_raw.csv"
    
    if not path.exists(): return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        df.columns = [str(c).lower().strip() for c in df.columns]
        if 'squad' in df.columns: df = df.rename(columns={'squad': 'team'})
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            # Filtro Temporada 25/26
            df = df[df['date'] > '2025-08-01'] 
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
            gf, ga = r['FTHG'], r['FTAG']
            sh, co, ca, fo = r['HS'], r['HC'], r['HY'], r['HF']
            tag = "(C)"
        else:
            gf, ga = r['FTAG'], r['FTHG']
            sh, co, ca, fo = r['AS'], r['AC'], r['AY'], r['AF']
            tag = "(F)"
            
        if gf > ga: res = '✅'
        elif gf == ga: res = '➖'
        else: res = '❌'
        
        stats['goals_for'].append(gf); stats['goals_against'].append(ga)
        stats['shots'].append(sh); stats['corners'].append(co)
        stats['cards'].append(ca); stats['fouls'].append(fo)
        stats['results'].append(res)
        log.append(f"{d_str} {res} {int(gf)}-{int(ga)} vs {opp} {tag}")

    count = len(matches)
    return {
        'gf': sum(stats['goals_for']) / count, 'ga': sum(stats['goals_against']) / count,
        'sh': sum(stats['shots']) / count, 'corn': sum(stats['corners']) / count,
        'card': sum(stats['cards']) / count, 'foul': sum(stats['fouls']) / count,
        'log': log, 'raw_results': stats['results']
    }

def normalize_str(s):
    if not isinstance(s, str): return str(s)
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')

def fuzzy_match_team(team_name, df_players):
    """Encuentra el nombre correcto del equipo en el archivo de jugadores"""
    if df_players.empty or 'team' not in df_players.columns: return None
    
    # 1. Intentar usar el MAPEO manual primero (lo más seguro)
    if team_name in TEAM_MAPPING:
        target = normalize_str(TEAM_MAPPING[team_name])
    else:
        target = normalize_str(team_name)
        
    player_teams = df_players['team'].dropna().unique()
    
    # 2. Búsqueda exacta normalizada
    for t in player_teams:
        if normalize_str(t) == target: return t
        
    # 3. Búsqueda parcial (contiene)
    for t in player_teams:
        norm = normalize_str(t)
        if target in norm or norm in target: return t
        
    return None # Si no encuentra nada

def get_player_rankings(df_players, team_name):
    real_team = fuzzy_match_team(team_name, df_players)
    if not real_team: return None, None, None
    
    df_p = df_players[df_players['team'] == real_team].copy()
    if df_p.empty: return None, None, None
    
    # Goleadores (Total)
    scorers = df_p.groupby('player')[['gls', 'ast', 'min']].sum().sort_values('gls', ascending=False).head(5)
    # Rematadores (Media)
    game_counts = df_p['player'].value_counts()
    valid_p = game_counts[game_counts >= 2].index
    shooters = df_p[df_p['player'].isin(valid_p)].groupby('player')[['sh', 'sot']].mean().sort_values('sh', ascending=False).head(5)
    # Leñeros (Media)
    bad_boys = df_p[df_p['player'].isin(valid_p)].groupby('player')[['fls', 'crdy']].mean().sort_values('fls', ascending=False).head(5)
    
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
                "Fecha": r['Date'].strftime("%d/%m/%Y"),
                "Local": r['HomeTeam'],
                "Res": f"{int(r['FTHG'])}-{int(r['FTAG'])}",
                "Visitante": r['AwayTeam'],
                "1": r.get('B365H', '-'), "X": r.get('B365D', '-'), "2": r.get('B365A', '-')
            })
        except: continue
    return pd.DataFrame(display_data)

# --- INTERFAZ ---
full_df = load_all_matches()
df_players = load_players()

# Sidebar Debug (Para que veas si carga jugadores)
st.sidebar.title("🤖 Analista Total")
if not df_players.empty:
    st.sidebar.success(f"✅ {len(df_players)} Stats de Jugadores cargadas.")
else:
    st.sidebar.error("❌ No hay datos de jugadores (revisa 'datos/jugadores_raw.csv')")

# Estilos CSS
st.markdown("""
<style>
    .win { color: #4CAF50; font-weight: bold; }
    .loss { color: #F44336; font-weight: bold; }
    .draw { color: #FFC107; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if full_df.empty:
    st.error("⚠️ Carpeta DATOS vacía. Sube CSVs a GitHub.")
else:
    all_teams = sorted(full_df[full_df['Date'] > '2025-08-01']['HomeTeam'].unique())
    if not all_teams: all_teams = sorted(full_df['HomeTeam'].unique())

    tabs = st.tabs(["🆚 Comparador PRO", "🛡️ Equipos", "⚽ Jugadores", "🏟️ Plantillas"])

    # ==============================================================================
    # TAB 1: COMPARADOR PRO
    # ==============================================================================
    with tabs[0]:
        c1, c2, c3 = st.columns([2, 2, 1])
        local = c1.selectbox("Local", all_teams, index=0)
        visitante = c2.selectbox("Visitante", all_teams, index=1)
        
        with c3:
            st.write("🛠️ **Filtros**")
            n_games = st.selectbox("Partidos", [5, 10, 20], index=0)
            
        st.divider()

        # LOGICA
        filter_loc = "Home" # Por defecto
        filter_vis = "Away" # Por defecto
        
        stats_loc = get_advanced_form(full_df, local, n_games, filter_loc)
        stats_vis = get_advanced_form(full_df, visitante, n_games, filter_vis)
        
        # COMPARATIVA EQUIPOS
        if stats_loc and stats_vis:
            st.subheader(f"📊 Estadísticas ({local} Casa vs {visitante} Fuera)")
            
            c_r1, c_r2 = st.columns(2)
            with c_r1: 
                racha_l = " ".join([f"<span class='{'win' if x=='✅' else 'loss' if x=='❌' else 'draw'}'>{x}</span>" for x in stats_loc['raw_results']])
                st.markdown(f"**Racha {local}:** {racha_l}", unsafe_allow_html=True)
            with c_r2:
                racha_v = " ".join([f"<span class='{'win' if x=='✅' else 'loss' if x=='❌' else 'draw'}'>{x}</span>" for x in stats_vis['raw_results']])
                st.markdown(f"**Racha {visitante}:** {racha_v}", unsafe_allow_html=True)

            comp_data = {
                "Métrica": ["Goles a Favor", "Goles en Contra", "Tiros Totales", "Córners", "Tarjetas", "Faltas"],
                f"{local}": [f"{stats_loc['gf']:.1f}", f"{stats_loc['ga']:.1f}", f"{stats_loc['sh']:.1f}", f"{stats_loc['corn']:.1f}", f"{stats_loc['card']:.1f}", f"{stats_loc['foul']:.1f}"],
                f"{visitante}": [f"{stats_vis['gf']:.1f}", f"{stats_vis['ga']:.1f}", f"{stats_vis['sh']:.1f}", f"{stats_vis['corn']:.1f}", f"{stats_vis['card']:.1f}", f"{stats_vis['foul']:.1f}"]
            }
            st.dataframe(pd.DataFrame(comp_data), hide_index=True, use_container_width=True)
        else:
            st.warning("Faltan datos de partidos recientes.")

        st.divider()

        # COMPARATIVA JUGADORES
        st.subheader("🔥 Top Jugadores (Media)")
        scorers_L, shooters_L, cards_L = get_player_rankings(df_players, local)
        scorers_V, shooters_V, cards_V = get_player_rankings(df_players, visitante)
        
        col_p_local, col_p_visit = st.columns(2)
        
        with col_p_local:
            st.markdown(f"### 🏠 {local}")
            if scorers_L is not None:
                st.caption("⚽ Goleadores")
                st.dataframe(scorers_L.rename(columns={'gls':'G','ast':'A','min':'Min'}), use_container_width=True)
                st.caption("🎯 Tiros por Partido")
                st.dataframe(shooters_L.rename(columns={'sh':'Tiros','sot':'Puerta'}).style.format("{:.2f}"), use_container_width=True)
                st.caption("🪓 Faltas por Partido")
                st.dataframe(cards_L.rename(columns={'fls':'Faltas','crdy':'Amarillas'}).style.format("{:.2f}"), use_container_width=True)
            else: st.info("Sin datos de jugadores (Revisa nombres).")

        with col_p_visit:
            st.markdown(f"### ✈️ {visitante}")
            if scorers_V is not None:
                st.caption("⚽ Goleadores")
                st.dataframe(scorers_V.rename(columns={'gls':'G','ast':'A','min':'Min'}), use_container_width=True)
                st.caption("🎯 Tiros por Partido")
                st.dataframe(shooters_V.rename(columns={'sh':'Tiros','sot':'Puerta'}).style.format("{:.2f}"), use_container_width=True)
                st.caption("🪓 Faltas por Partido")
                st.dataframe(cards_V.rename(columns={'fls':'Faltas','crdy':'Amarillas'}).style.format("{:.2f}"), use_container_width=True)
            else: st.info("Sin datos de jugadores (Revisa nombres).")

        st.divider()

        # HISTÓRICO H2H
        h2h_df = get_h2h_history(full_df, local, visitante)
        with st.expander("📚 Ver Historial H2H (2004-2026)", expanded=False):
            if h2h_df is not None:
                st.dataframe(h2h_df, hide_index=True, use_container_width=True)
            else: st.write("No hay partidos previos.")

    # ==============================================================================
    # TAB 2: EQUIPOS
    # ==============================================================================
    with tabs[1]:
        tm = st.selectbox("Equipo", all_teams, key="tab2_tm")
        stats_gen = get_advanced_form(full_df, tm, 38, 'General')
        if stats_gen:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Goles/P", f"{stats_gen['gf']:.2f}")
            c2.metric("Recibidos/P", f"{stats_gen['ga']:.2f}")
            c3.metric("Tiros/P", f"{stats_gen['sh']:.2f}")
            c4.metric("Córners/P", f"{stats_gen['corn']:.2f}")
            st.write("**Últimos partidos:**")
            for l in stats_gen['log'][-10:]: st.text(l)

    # ==============================================================================
    # TAB 3: JUGADORES (BUSCADOR ARREGLADO)
    # ==============================================================================
    with tabs[2]:
        st.header("🔎 Buscador")
        if not df_players.empty:
            c1, c2 = st.columns(2)
            # Primero elegimos el equipo DEL LISTADO DE PARTIDOS para asegurar coincidencia
            team_sel = c1.selectbox("Equipo", all_teams, key="tab3_tm")
            
            # Buscamos el nombre real en el archivo de jugadores
            real_team_name = fuzzy_match_team(team_sel, df_players)
            
            if real_team_name:
                players_list = sorted(df_players[df_players['team'] == real_team_name]['player'].unique())
                pl_sel = c2.selectbox("Jugador", players_list)
                
                p_stats = df_players[df_players['player'] == pl_sel].sort_values('date', ascending=False)
                st.write(f"**Stats de {pl_sel}:**")
                st.dataframe(p_stats[['date','game','min','gls','ast','sh','sot','fls','crdy']], hide_index=True, use_container_width=True)
            else:
                st.warning(f"No encuentro datos de jugadores para '{team_sel}'.")

    # ==============================================================================
    # TAB 4: PLANTILLAS (ARREGLADO)
    # ==============================================================================
    with tabs[3]:
        st.header("📊 Plantilla")
        if not df_players.empty:
            team_sq = st.selectbox("Equipo", all_teams, key="tab4_tm")
            real_team_sq = fuzzy_match_team(team_sq, df_players)
            
            if real_team_sq:
                df_sq = df_players[df_players['team'] == real_team_sq]
                summ = df_sq.groupby('player').agg({
                    'min':'sum', 'gls':'sum', 'ast':'sum',
                    'sh':'mean', 'sot':'mean', 'fls':'mean', 'crdy':'sum'
                }).reset_index()
                
                st.dataframe(
                    summ.rename(columns={'min':'Min','gls':'G','ast':'A','sh':'Tiros/P','sot':'Puerta/P','fls':'Faltas/P','crdy':'Amarillas'}).style.format("{:.2f}", subset=['Tiros/P','Puerta/P','Faltas/P']),
                    hide_index=True, use_container_width=True, height=700
                )
            else:
                st.warning(f"Sin datos de plantilla para '{team_sq}'.")
