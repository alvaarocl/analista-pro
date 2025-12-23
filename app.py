import streamlit as st
import pandas as pd
import news_engine
from pathlib import Path
import unicodedata

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analista Pro Histórico", layout="wide", page_icon="⚽")

# --- DICCIONARIOS ---
PLAYER_DICT = {
    "player": "Jugador", "team": "Equipo", "date": "Fecha",
    "sh": "Remates", "sot": "A Puerta", "fls": "Faltas", 
    "crdy": "T. Amarillas", "gls": "Goles", "ast": "Asistencias",
    "min": "Minutos", "game_count": "PJ"
}

# --- CARGA DE DATOS (HISTÓRICO + ACTUAL) ---
@st.cache_data
def load_all_matches():
    # Carga TODOS los CSVs históricos
    files = list(Path("datos").glob("*.csv"))
    files = [f for f in files if "jugadores" not in f.name]
    
    if not files:
        st.error("⚠️ Carpeta datos/ vacía. Ejecuta data_updater.py en tu PC primero.")
        return pd.DataFrame()
        
    dfs = []
    for f in files:
        try:
            # encoding='latin1' es vital para archivos antiguos de football-data
            d = pd.read_csv(f, encoding='latin1') 
            
            # Normalizar columnas (a veces cambian mayúsculas/minúsculas en 20 años)
            # Mapeamos columnas clave a nombres estándar
            col_map = {
                'HomeTeam': 'HomeTeam', 'AwayTeam': 'AwayTeam', 
                'FTHG': 'FTHG', 'FTAG': 'FTAG', 
                'Date': 'Date',
                'B365H': 'B365H', 'B365D': 'B365D', 'B365A': 'B365A', # Cuotas Bet365
                'HS': 'HS', 'AS': 'AS', 'HST': 'HST', 'AST': 'AST', # Tiros
                'HC': 'HC', 'AC': 'AC', 'HY': 'HY', 'AY': 'AY' # Corners/Cards
            }
            # Renombrar si existen variaciones ligeras o mantener
            # (Simplificación para este ejemplo, asumimos estructura estándar de football-data)
            
            if 'Date' in d.columns:
                # Manejo de formatos de fecha mixtos (dd/mm/yy y dd/mm/yyyy)
                d['Date'] = pd.to_datetime(d['Date'], dayfirst=True, errors='coerce')
            
            dfs.append(d)
        except: continue
        
    if not dfs: return pd.DataFrame()
    
    # Concatenar todo el historial
    full_df = pd.concat(dfs, ignore_index=True)
    return full_df.sort_values('Date', ascending=True)

@st.cache_data
def load_players():
    # Jugadores SOLO de la temporada actual (cargados desde tu PC)
    path = Path("datos/jugadores_raw.csv")
    if not path.exists(): return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        df.columns = [str(c).lower().strip() for c in df.columns]
        if 'squad' in df.columns: df = df.rename(columns={'squad': 'team'})
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            # Filtro estricto: Solo temporada 25/26
            df = df[df['date'] > '2025-08-01']
        return df
    except: return pd.DataFrame()

# --- FUNCIONES LÓGICAS ---

def get_h2h_history(df_history, team1, team2):
    """
    Busca TODOS los enfrentamientos entre estos dos equipos en la base de datos.
    Devuelve un DataFrame con Fecha, Resultado y Cuotas.
    """
    # Filtro: (Local=A Y Vis=B) O (Local=B Y Vis=A)
    mask = ((df_history['HomeTeam'] == team1) & (df_history['AwayTeam'] == team2)) | \
           ((df_history['HomeTeam'] == team2) & (df_history['AwayTeam'] == team1))
    
    h2h = df_history[mask].sort_values('Date', ascending=False).copy()
    
    if h2h.empty: return None
    
    # Formatear para mostrar
    h2h['Resultado'] = h2h.apply(lambda x: f"{x['HomeTeam']} {int(x['FTHG'])}-{int(x['FTAG'])} {x['AwayTeam']}", axis=1)
    
    # Seleccionar columnas interesantes (Fecha, Resultado, Cuotas)
    cols = ['Date', 'Resultado', 'B365H', 'B365D', 'B365A']
    # Solo las que existan
    cols = [c for c in cols if c in h2h.columns]
    
    return h2h[cols]

def get_recent_form(df_history, team, venue_filter='All'):
    """
    Calcula la forma RECIENTE usando solo los partidos de la temporada 25/26.
    """
    # 1. Filtro de fecha: Solo temporada actual
    df_current = df_history[df_history['Date'] > '2025-08-01']
    
    if df_current.empty: return None
    
    # 2. Filtro Local/Visitante
    if venue_filter == 'Home': matches = df_current[df_current['HomeTeam'] == team]
    elif venue_filter == 'Away': matches = df_current[df_current['AwayTeam'] == team]
    else: matches = df_current[(df_current['HomeTeam'] == team) | (df_current['AwayTeam'] == team)]
        
    matches = matches.sort_values('Date').tail(5)
    if matches.empty: return None
    
    stats = {'goals': [], 'shots': [], 'corners': [], 'cards': [], 'fouls': []}
    history = []

    for _, r in matches.iterrows():
        is_home = (r['HomeTeam'] == team)
        opp = r['AwayTeam'] if is_home else r['HomeTeam']
        
        hg = r['FTHG'] if pd.notnull(r['FTHG']) else 0
        ag = r['FTAG'] if pd.notnull(r['FTAG']) else 0
        
        if is_home:
            res = '✅' if hg > ag else ('❌' if hg < ag else '➖')
            stats['goals'].append(hg); stats['shots'].append(r.get('HS', 0))
            stats['corners'].append(r.get('HC', 0)); stats['cards'].append(r.get('HY', 0))
            stats['fouls'].append(r.get('HF', 0))
            history.append(f"{res} {int(hg)}-{int(ag)} vs {opp} (C)")
        else:
            res = '✅' if ag > hg else ('❌' if ag < hg else '➖')
            stats['goals'].append(ag); stats['shots'].append(r.get('AS', 0))
            stats['corners'].append(r.get('AC', 0)); stats['cards'].append(r.get('AY', 0))
            stats['fouls'].append(r.get('AF', 0))
            history.append(f"{res} {int(ag)}-{int(hg)} vs {opp} (F)")

    avgs = {k: sum(v)/len(v) if v else 0 for k, v in stats.items()}
    avgs['match_log'] = history
    return avgs

# --- FUNCIONES AUXILIARES JUGADORES ---
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

def prepare_display_tables(df_players, team_name):
    real_team = fuzzy_match_team(team_name, df_players)
    df_p = df_players[df_players['team'] == real_team].copy()
    if df_p.empty: return None, None
    
    # Top Rematadores
    df_sh = df_p.groupby('player')[['sh', 'sot']].mean().sort_values('sh', ascending=False).head(6)
    df_sh = df_sh.rename(columns={'sh': 'Remates', 'sot': 'A Puerta'})
    
    # Top Leñeros
    df_fls = df_p.groupby('player')[['fls', 'crdy']].mean().sort_values('fls', ascending=False).head(6)
    df_fls = df_fls.rename(columns={'fls': 'Faltas', 'crdy': 'Tarjetas'})
    
    return df_sh, df_fls

# --- INTERFAZ ---
full_df = load_all_matches() # Carga historial completo
df_players = load_players()

st.sidebar.title("🤖 Analista Pro")

if not full_df.empty:
    min_y = full_df['Date'].min().year
    max_y = full_df['Date'].max().year
    st.sidebar.success(f"📚 Base de Datos: {min_y} - {max_y}")
    
    # Lista de equipos actuales (sacada de los últimos 6 meses para no mostrar equipos de 2004 que ya no están)
    recent_teams = full_df[full_df['Date'] > '2025-01-01']['HomeTeam'].unique()
    teams = sorted(recent_teams) if len(recent_teams) > 0 else sorted(full_df['HomeTeam'].unique())
else:
    teams = []
    st.sidebar.warning("⚠️ Sin datos.")

tabs = st.tabs(["📉 Comparador", "📚 Histórico H2H", "⚽ Jugador"])

# ==============================================================================
# TAB 1: COMPARADOR (FORMA ACTUAL 25/26)
# ==============================================================================
with tabs[0]:
    st.header("📉 Forma Actual (Temporada 25/26)")
    
    col1, col2 = st.columns(2)
    local = col1.selectbox("Local", teams, index=0)
    visitante = col2.selectbox("Visitante", teams, index=1)
    
    if st.button("📊 ANALIZAR PARTIDO", type="primary"):
        # 1. Forma Reciente
        spec_loc = get_recent_form(full_df, local, 'Home')
        spec_vis = get_recent_form(full_df, visitante, 'Away')
        
        # 2. Jugadores
        sh_loc, fl_loc = prepare_display_tables(df_players, local)
        sh_vis, fl_vis = prepare_display_tables(df_players, visitante)
        
        # 3. Noticias
        with st.spinner("Noticias..."):
            try: news = news_engine.get_live_context(local, visitante)
            except: news = {}

        st.divider()
        
        # --- SECCIÓN VISUAL ---
        c_h1, c_h2 = st.columns(2)
        with c_h1:
            st.subheader(f"🏠 {local} (En Casa)")
            if spec_loc:
                for log in spec_loc['match_log']: st.caption(log)
                st.write(f"**Goles:** {spec_loc['goals']:.2f} | **Córners:** {spec_loc['corners']:.2f} | **Tarjetas:** {spec_loc['cards']:.2f}")
            else: st.warning("Sin datos recientes en casa.")
            
            st.markdown("---")
            st.write("**Top Jugadores:**")
            if sh_loc is not None: st.dataframe(sh_loc.style.format("{:.2f}"))

        with c_h2:
            st.subheader(f"✈️ {visitante} (Fuera)")
            if spec_vis:
                for log in spec_vis['match_log']: st.caption(log)
                st.write(f"**Goles:** {spec_vis['goals']:.2f} | **Córners:** {spec_vis['corners']:.2f} | **Tarjetas:** {spec_vis['cards']:.2f}")
            else: st.warning("Sin datos recientes fuera.")
            
            st.markdown("---")
            st.write("**Top Jugadores:**")
            if sh_vis is not None: st.dataframe(sh_vis.style.format("{:.2f}"))

        with st.expander("📰 Noticias Recientes"):
            st.write(news.get('texto', 'Sin noticias.'))

# ==============================================================================
# TAB 2: HISTÓRICO H2H (LA NOVEDAD)
# ==============================================================================
with tabs[1]:
    st.header("📚 Historial de Enfrentamientos (Desde 2004)")
    st.markdown("Aquí puedes ver qué pasó en el pasado entre estos dos equipos y **qué cuotas (Bet365)** había.")
    
    c_h2h_1, c_h2h_2 = st.columns(2)
    t1 = c_h2h_1.selectbox("Equipo 1", teams, index=0, key="h2h_1")
    t2 = c_h2h_2.selectbox("Equipo 2", teams, index=1, key="h2h_2")
    
    h2h_data = get_h2h_history(full_df, t1, t2)
    
    if h2h_data is not None:
        st.success(f"Se han encontrado {len(h2h_data)} enfrentamientos previos.")
        
        # Formatear la tabla para que se vea bonita
        # Renombramos columnas para que se entienda mejor
        display_h2h = h2h_data.rename(columns={
            'Date': 'Fecha',
            'B365H': f'Cuota {t1} (o Local)',
            'B365D': 'Cuota Empate',
            'B365A': f'Cuota {t2} (o Visitante)'
        })
        
        st.dataframe(
            display_h2h,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY")
            }
        )
    else:
        st.info("No hay enfrentamientos registrados en la base de datos entre estos dos equipos.")

# ==============================================================================
# TAB 3: JUGADOR INDIVIDUAL
# ==============================================================================
with tabs[2]:
    st.header("⚽ Análisis Individual")
    if not df_players.empty:
        tm = st.selectbox("Equipo", sorted(df_players['team'].dropna().unique()), key="p_tm")
        pl = st.selectbox("Jugador", sorted(df_players[df_players['team']==tm]['player'].unique()), key="p_pl")
        stats = df_players[df_players['player']==pl].sort_values('date', ascending=False)
        st.dataframe(stats[['date','game','sh','sot','fls','crdy']].rename(columns=PLAYER_DICT), hide_index=True)
