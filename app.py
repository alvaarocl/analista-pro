import streamlit as st
import pandas as pd
import news_engine
from pathlib import Path
import unicodedata

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analista Pro Total", layout="wide", page_icon="⚽")

# --- FUNCIÓN INTELIGENTE PARA ENCONTRAR DATOS (Mayúsculas/Minúsculas) ---
def get_data_dir():
    """Busca la carpeta de datos ya sea DATOS o datos"""
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
            d.columns = [c.strip() for c in d.columns] # Limpiar espacios
            
            # Normalizar columnas esenciales
            if 'Date' in d.columns:
                d['Date'] = pd.to_datetime(d['Date'], dayfirst=True, errors='coerce')
            
            # Asegurar que existen las columnas de estadísticas (rellenar con 0 si faltan)
            for col in ['HS','AS','HST','AST','HC','AC','HF','AF','HY','AY','HR','AR']:
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
            df = df[df['date'] > '2025-08-01'] # Solo temporada actual
        return df
    except: return pd.DataFrame()

# --- LÓGICA DE ESTADÍSTICAS AVANZADAS ---

def get_advanced_form(df, team, games=5, filter_mode='Auto'):
    """
    Calcula estadísticas avanzadas (Tiros, Córners, etc.)
    filter_mode: 'Auto' (Casa para Local, Fuera para Vis), 'General' (Todo), 'Home', 'Away'
    """
    if df.empty: return None
    
    # 1. Filtro Temporada Actual
    df_curr = df[df['Date'] > '2025-08-01']
    
    # 2. Filtro de Lugar (Home/Away/All)
    if filter_mode == 'Home':
        matches = df_curr[df_curr['HomeTeam'] == team]
    elif filter_mode == 'Away':
        matches = df_curr[df_curr['AwayTeam'] == team]
    else: # General
        matches = df_curr[(df_curr['HomeTeam'] == team) | (df_curr['AwayTeam'] == team)]
    
    # 3. Cortar por número de partidos
    matches = matches.sort_values('Date', ascending=True).tail(games)
    
    if matches.empty: return None
    
    stats = {
        'goals_for': [], 'goals_against': [],
        'shots': [], 'shots_target': [],
        'corners': [], 'cards': [], 'fouls': [],
        'results': [] # W/D/L
    }
    
    log = []

    for _, r in matches.iterrows():
        is_home = (r['HomeTeam'] == team)
        opp = r['AwayTeam'] if is_home else r['HomeTeam']
        d_str = r['Date'].strftime("%d/%m")
        
        # Extracción de datos según si es local o visitante
        if is_home:
            gf, ga = r['FTHG'], r['FTAG']
            sh, sot = r['HS'], r['HST']
            co, ca, fo = r['HC'], r['HY'], r['HF']
            loc_tag = "(C)"
        else:
            gf, ga = r['FTAG'], r['FTHG']
            sh, sot = r['AS'], r['AST']
            co, ca, fo = r['AC'], r['AY'], r['AF']
            loc_tag = "(F)"
            
        # Resultado
        if gf > ga: res = '✅'
        elif gf == ga: res = '➖'
        else: res = '❌'
        
        stats['goals_for'].append(gf); stats['goals_against'].append(ga)
        stats['shots'].append(sh); stats['shots_target'].append(sot)
        stats['corners'].append(co); stats['cards'].append(ca); stats['fouls'].append(fo)
        stats['results'].append(res)
        
        log.append(f"{d_str} {res} {int(gf)}-{int(ga)} vs {opp} {loc_tag}")

    # Cálculos de Medias
    count = len(matches)
    avgs = {
        'count': count,
        'gf': sum(stats['goals_for']) / count,
        'ga': sum(stats['goals_against']) / count,
        'sh': sum(stats['shots']) / count,
        'sot': sum(stats['shots_target']) / count,
        'corn': sum(stats['corners']) / count,
        'card': sum(stats['cards']) / count,
        'foul': sum(stats['fouls']) / count,
        'log': log,
        'raw_results': stats['results'] # Para mostrar racha visual
    }
    return avgs

def normalize_str(s):
    if not isinstance(s, str): return str(s)
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')

def fuzzy_match_team(team_name, df_players):
    if df_players.empty or 'team' not in df_players.columns: return team_name
    target = normalize_str(team_name)
    player_teams = df_players['team'].dropna().unique()
    for t in player_teams:
        if normalize_str(t) == target: return t
    for t in player_teams:
        norm = normalize_str(t)
        if target in norm or norm in target: return t
    return team_name

def get_player_rankings(df_players, team_name):
    """Devuelve 3 DataFrames: Goleadores, Rematadores, Leñeros"""
    real_team = fuzzy_match_team(team_name, df_players)
    df_p = df_players[df_players['team'] == real_team].copy()
    if df_p.empty: return None, None, None
    
    # Estadísticas TOTALES (Sumas) y MEDIAS
    # Goleadores (Suma total goles)
    scorers = df_p.groupby('player')[['gls', 'ast', 'min']].sum().sort_values('gls', ascending=False).head(5)
    
    # Rematadores (Media por partido, min 3 partidos)
    game_counts = df_p['player'].value_counts()
    valid_players = game_counts[game_counts >= 3].index
    df_valid = df_p[df_p['player'].isin(valid_players)]
    
    shooters = df_valid.groupby('player')[['sh', 'sot']].mean().sort_values('sh', ascending=False).head(5)
    
    # Tarjeteros (Suma total)
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

# --- CSS PARA ESTILO ---
st.markdown("""
<style>
    .big-font { font-size:18px !important; font-weight: bold; }
    .stat-box { background-color: #262730; padding: 10px; border-radius: 5px; text-align: center; }
    .win { color: #4CAF50; font-weight: bold; }
    .loss { color: #F44336; font-weight: bold; }
    .draw { color: #FFC107; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
if full_df.empty:
    st.sidebar.error("⚠️ Carpeta DATOS vacía. Sube CSVs a GitHub.")
else:
    all_teams = sorted(full_df[full_df['Date'] > '2025-08-01']['HomeTeam'].unique())
    if not all_teams: all_teams = sorted(full_df['HomeTeam'].unique())

tabs = st.tabs(["🆚 Comparador PRO", "🛡️ Equipos", "⚽ Jugadores", "🏟️ Plantillas"])

# ==============================================================================
# TAB 1: COMPARADOR PRO (REDISEÑADO)
# ==============================================================================
with tabs[0]:
    if full_df.empty:
        st.warning("No hay datos cargados.")
    else:
        # 1. SELECTORES PRINCIPALES
        c1, c2, c3 = st.columns([2, 2, 1])
        local = c1.selectbox("Local", all_teams, index=0)
        visitante = c2.selectbox("Visitante", all_teams, index=1)
        
        # Filtros de Análisis
        with c3:
            st.write("🛠️ **Filtros**")
            n_games = st.selectbox("Partidos", [5, 10, 20], index=0)
            
        st.divider()

        # 2. LOGICA DE DATOS
        # Por defecto: Local analizamos sus partidos en Casa ("Home") y Visitante fuera ("Away")
        # Pero podemos cambiarlo si el usuario quiere ver "Forma General"
        
        mode_loc = st.radio(f"Ver datos de {local} como:", ["En Casa (Recomendado)", "Global (Todos)"], horizontal=True, key="m_loc")
        filter_loc = "Home" if "Casa" in mode_loc else "General"
        
        mode_vis = st.radio(f"Ver datos de {visitante} como:", ["Fuera (Recomendado)", "Global (Todos)"], horizontal=True, key="m_vis")
        filter_vis = "Away" if "Fuera" in mode_vis else "General"
        
        stats_loc = get_advanced_form(full_df, local, n_games, filter_loc)
        stats_vis = get_advanced_form(full_df, visitante, n_games, filter_vis)
        
        # 3. COMPARATIVA VISUAL (ESTADÍSTICAS)
        if stats_loc and stats_vis:
            st.subheader(f"📊 Promedios (Últimos {n_games} Partidos)")
            
            # RACHA VISUAL
            c_r1, c_r2 = st.columns(2)
            with c_r1: 
                racha_l = " ".join([f"<span class='{'win' if x=='✅' else 'loss' if x=='❌' else 'draw'}'>{x}</span>" for x in stats_loc['raw_results']])
                st.markdown(f"**Racha {local}:** {racha_l}", unsafe_allow_html=True)
            with c_r2:
                racha_v = " ".join([f"<span class='{'win' if x=='✅' else 'loss' if x=='❌' else 'draw'}'>{x}</span>" for x in stats_vis['raw_results']])
                st.markdown(f"**Racha {visitante}:** {racha_v}", unsafe_allow_html=True)

            # TABLA DE COMPARACIÓN
            comp_data = {
                "Métrica": ["Goles a Favor", "Goles en Contra", "Tiros Totales", "Tiros a Puerta", "Córners", "Tarjetas", "Faltas"],
                f"{local}": [
                    f"{stats_loc['gf']:.1f}", f"{stats_loc['ga']:.1f}", 
                    f"{stats_loc['sh']:.1f}", f"{stats_loc['sot']:.1f}", 
                    f"{stats_loc['corn']:.1f}", f"{stats_loc['card']:.1f}", f"{stats_loc['foul']:.1f}"
                ],
                f"{visitante}": [
                    f"{stats_vis['gf']:.1f}", f"{stats_vis['ga']:.1f}", 
                    f"{stats_vis['sh']:.1f}", f"{stats_vis['sot']:.1f}", 
                    f"{stats_vis['corn']:.1f}", f"{stats_vis['card']:.1f}", f"{stats_vis['foul']:.1f}"
                ]
            }
            st.dataframe(pd.DataFrame(comp_data), hide_index=True, use_container_width=True)
            
            # Logs de partidos
            with st.expander(f"Ver detalle de los últimos partidos utilizados"):
                cl1, cl2 = st.columns(2)
                with cl1:
                    st.write(f"**{local}**")
                    for l in stats_loc['log']: st.text(l)
                with cl2:
                    st.write(f"**{visitante}**")
                    for l in stats_vis['log']: st.text(l)
        else:
            st.warning("Faltan datos para generar las medias.")

        st.divider()

        # 4. COMPARATIVA JUGADORES (3 TABLAS)
        st.subheader("🔥 Jugadores Clave (Top 5)")
        
        scorers_L, shooters_L, cards_L = get_player_rankings(df_players, local)
        scorers_V, shooters_V, cards_V = get_player_rankings(df_players, visitante)
        
        col_p_local, col_p_visit = st.columns(2)
        
        # --- COLUMNA LOCAL ---
        with col_p_local:
            st.markdown(f"### 🏠 {local}")
            if scorers_L is not None:
                st.caption("⚽ Máximos Goleadores (Total)")
                st.dataframe(scorers_L.rename(columns={'gls':'Goles','ast':'Asist','min':'Mins'}), use_container_width=True)
                
                st.caption("🎯 Francotiradores (Media Tiros/Partido)")
                st.dataframe(shooters_L.rename(columns={'sh':'Tiros','sot':'Puerta'}).style.format("{:.2f}"), use_container_width=True)
                
                st.caption("🪓 Tarjetas y Faltas (Media)")
                st.dataframe(cards_L.rename(columns={'fls':'Faltas','crdy':'Amarillas'}).style.format("{:.2f}"), use_container_width=True)
            else:
                st.info("Sin datos de jugadores.")

        # --- COLUMNA VISITANTE ---
        with col_p_visit:
            st.markdown(f"### ✈️ {visitante}")
            if scorers_V is not None:
                st.caption("⚽ Máximos Goleadores (Total)")
                st.dataframe(scorers_V.rename(columns={'gls':'Goles','ast':'Asist','min':'Mins'}), use_container_width=True)
                
                st.caption("🎯 Francotiradores (Media Tiros/Partido)")
                st.dataframe(shooters_V.rename(columns={'sh':'Tiros','sot':'Puerta'}).style.format("{:.2f}"), use_container_width=True)
                
                st.caption("🪓 Tarjetas y Faltas (Media)")
                st.dataframe(cards_V.rename(columns={'fls':'Faltas','crdy':'Amarillas'}).style.format("{:.2f}"), use_container_width=True)
            else:
                st.info("Sin datos de jugadores.")

        st.divider()

        # 5. HISTÓRICO H2H (AL FINAL)
        h2h_df = get_h2h_history(full_df, local, visitante)
        with st.expander("📚 Ver Historial de Enfrentamientos Directos (H2H 2004-2026)", expanded=False):
            if h2h_df is not None:
                st.dataframe(h2h_df, hide_index=True, use_container_width=True)
            else:
                st.write("No hay partidos previos registrados.")
        
        # Noticias
        with st.expander("📰 Últimas Noticias (Contexto)", expanded=False):
             with st.spinner("Cargando..."):
                try: 
                    ctx = news_engine.get_live_context(local, visitante)
                    st.write(ctx.get('texto', 'Sin noticias.'))
                except: st.write("No disponible.")

# ==============================================================================
# TAB 2: EQUIPOS (SIMPLE)
# ==============================================================================
with tabs[1]:
    if not full_df.empty:
        tm = st.selectbox("Selecciona Equipo", all_teams, key="tab2_tm")
        st.subheader(f"Estadísticas Generales: {tm}")
        stats_gen = get_advanced_form(full_df, tm, 38, 'General') # Toda la temp
        
        if stats_gen:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Goles/Partido", f"{stats_gen['gf']:.2f}")
            c2.metric("Recibidos/Partido", f"{stats_gen['ga']:.2f}")
            c3.metric("Tiros/Partido", f"{stats_gen['sh']:.2f}")
            c4.metric("Córners/Partido", f"{stats_gen['corn']:.2f}")
            st.write("Últimos partidos:")
            for l in stats_gen['log'][-10:]: st.text(l)

# ==============================================================================
# TAB 3: JUGADORES (BUSCADOR)
# ==============================================================================
with tabs[2]:
    st.header("🔎 Buscador de Jugador")
    if not df_players.empty:
        c_p1, c_p2 = st.columns(2)
        eq_p = c_p1.selectbox("Equipo", all_teams, key="tab3_tm")
        
        # Filtrar jugadores de ese equipo
        real_eq = fuzzy_match_team(eq_p, df_players)
        players_list = sorted(df_players[df_players['team'] == real_eq]['player'].unique())
        
        pl_sel = c_p2.selectbox("Jugador", players_list)
        
        # Mostrar stats del jugador
        p_stats = df_players[df_players['player'] == pl_sel].sort_values('date', ascending=False)
        
        st.write(f"**Últimos partidos de {pl_sel}:**")
        st.dataframe(p_stats[['date','game','min','gls','ast','sh','sot','fls','crdy']], hide_index=True, use_container_width=True)

# ==============================================================================
# TAB 4: PLANTILLAS (TABLA TOTAL)
# ==============================================================================
with tabs[3]:
    st.header("📊 Plantilla Completa")
    if not df_players.empty:
        eq_sq = st.selectbox("Equipo", all_teams, key="tab4_tm")
        real_eq_sq = fuzzy_match_team(eq_sq, df_players)
        
        df_sq = df_players[df_players['team'] == real_eq_sq]
        
        # Agrupar totales
        summ = df_sq.groupby('player').agg({
            'min':'sum', 'gls':'sum', 'ast':'sum',
            'sh':'mean', 'sot':'mean', 'fls':'mean', 'crdy':'sum'
        }).reset_index()
        
        st.dataframe(
            summ.rename(columns={'min':'Minutos','gls':'Goles','ast':'Asist','sh':'Tiros/P','sot':'Puerta/P','fls':'Faltas/P','crdy':'Amarillas'}),
            hide_index=True, use_container_width=True, height=700
        )
