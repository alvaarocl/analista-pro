import streamlit as st
import pandas as pd
import news_engine
from pathlib import Path
import unicodedata

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analista Pro Total", layout="wide", page_icon="⚽")

# --- DICCIONARIOS ---
PLAYER_DICT = {
    "player": "Jugador", "team": "Equipo", "date": "Fecha",
    "sh": "Remates", "sot": "A Puerta", "fls": "Faltas", 
    "crdy": "T. Amarillas", "gls": "Goles", "ast": "Asistencias",
    "min": "Minutos", "game_count": "PJ"
}

# --- CARGA DE DATOS (BLINDADA) ---
@st.cache_data
def load_all_matches():
    # Busca CSVs en la carpeta datos
    files = list(Path("datos").glob("*.csv"))
    files = [f for f in files if "jugadores" not in f.name]
    
    if not files:
        # Si no hay archivos, devolvemos DF vacío pero no fallamos
        return pd.DataFrame()
        
    dfs = []
    for f in files:
        try:
            # encoding='latin1' lee archivos antiguos sin error
            d = pd.read_csv(f, encoding='latin1')
            
            # --- LIMPIEZA CRÍTICA DE COLUMNAS ---
            # Quita espacios en blanco: "HomeTeam " -> "HomeTeam"
            d.columns = [c.strip() for c in d.columns]
            
            # Verificar que tiene las columnas mínimas, si no, saltar archivo
            if 'HomeTeam' not in d.columns or 'AwayTeam' not in d.columns:
                continue

            if 'Date' in d.columns:
                d['Date'] = pd.to_datetime(d['Date'], dayfirst=True, errors='coerce')
            
            dfs.append(d)
        except: continue
        
    if not dfs: return pd.DataFrame()
    
    # Concatenar todo y ordenar
    full_df = pd.concat(dfs, ignore_index=True)
    return full_df.sort_values('Date', ascending=True)

@st.cache_data
def load_players():
    path = Path("datos/jugadores_raw.csv")
    if not path.exists(): return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # Corrección nombres
        if 'squad' in df.columns: df = df.rename(columns={'squad': 'team'})
        
        # Filtro Temporada Actual (desde Agosto 2025)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df[df['date'] > '2025-08-01']
            
        return df
    except: return pd.DataFrame()

# --- LÓGICA DE NEGOCIO ---

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

def get_stats_pack_current(df, team, venue_filter='All'):
    """Calcula estadísticas SOLO de la temporada actual (últimos 5 partidos)."""
    if df.empty: return None
    
    # 1. Filtro Temporada Actual
    df_curr = df[df['Date'] > '2025-08-01']
    if df_curr.empty: return None

    # 2. Filtro Local/Visitante
    if venue_filter == 'Home': matches = df_curr[df_curr['HomeTeam'] == team]
    elif venue_filter == 'Away': matches = df_curr[df_curr['AwayTeam'] == team]
    else: matches = df_curr[(df_curr['HomeTeam'] == team) | (df_curr['AwayTeam'] == team)]
        
    matches = matches.sort_values('Date').tail(5)
    if matches.empty: return None
    
    stats = {'goals': [], 'shots': [], 'corners': [], 'cards': [], 'fouls': []}
    history = []

    for _, r in matches.iterrows():
        is_home = (r['HomeTeam'] == team)
        opp = r['AwayTeam'] if is_home else r['HomeTeam']
        d_str = r['Date'].strftime("%d/%m")
        
        if is_home:
            hg, ag = r['FTHG'], r['FTAG']
            res = '✅' if hg > ag else ('❌' if hg < ag else '➖')
            stats['goals'].append(hg); stats['shots'].append(r.get('HS', 0))
            stats['corners'].append(r.get('HC', 0)); stats['cards'].append(r.get('HY', 0))
            stats['fouls'].append(r.get('HF', 0))
            history.append(f"{d_str} {res} {int(hg)}-{int(ag)} vs {opp} (C)")
        else:
            hg, ag = r['FTHG'], r['FTAG']
            res = '✅' if ag > hg else ('❌' if ag < hg else '➖')
            stats['goals'].append(ag); stats['shots'].append(r.get('AS', 0))
            stats['corners'].append(r.get('AC', 0)); stats['cards'].append(r.get('AY', 0))
            stats['fouls'].append(r.get('AF', 0))
            history.append(f"{d_str} {res} {int(ag)}-{int(hg)} vs {opp} (F)")

    avgs = {k: sum(v)/len(v) if v else 0 for k, v in stats.items()}
    avgs['count'] = len(matches)
    avgs['match_log'] = history
    return avgs

def get_h2h_history(df_history, team1, team2):
    """Obtiene el historial completo desde 2004 entre dos equipos."""
    if df_history.empty: return None
    
    # Filtro cruzado
    mask = ((df_history['HomeTeam'] == team1) & (df_history['AwayTeam'] == team2)) | \
           ((df_history['HomeTeam'] == team2) & (df_history['AwayTeam'] == team1))
    
    h2h = df_history[mask].sort_values('Date', ascending=False)
    if h2h.empty: return None
    
    # Formato simple para la tabla
    display_data = []
    for _, r in h2h.iterrows():
        try:
            d_str = r['Date'].strftime("%d/%m/%Y")
            local = r['HomeTeam']
            visit = r['AwayTeam']
            res = f"{int(r['FTHG'])}-{int(r['FTAG'])}"
            # Cuotas si existen
            c1 = r.get('B365H', '-')
            cX = r.get('B365D', '-')
            c2 = r.get('B365A', '-')
            
            display_data.append({
                "Fecha": d_str,
                "Local": local,
                "Resultado": res,
                "Visitante": visit,
                "1": c1, "X": cX, "2": c2
            })
        except: continue
            
    return pd.DataFrame(display_data)

def get_team_general_stats(df, team):
    """Estadísticas generales de un equipo en la temporada actual (Tab 2)"""
    if df.empty: return None
    df_curr = df[df['Date'] > '2025-08-01']
    matches = df_curr[(df_curr['HomeTeam'] == team) | (df_curr['AwayTeam'] == team)]
    
    if matches.empty: return None
    
    played = len(matches)
    wins = 0; draws = 0; losses = 0
    gf = 0; ga = 0
    
    for _, r in matches.iterrows():
        if r['HomeTeam'] == team:
            gf += r['FTHG']; ga += r['FTAG']
            if r['FTHG'] > r['FTAG']: wins += 1
            elif r['FTHG'] == r['FTAG']: draws += 1
            else: losses += 1
        else:
            gf += r['FTAG']; ga += r['FTHG']
            if r['FTAG'] > r['FTHG']: wins += 1
            elif r['FTAG'] == r['FTHG']: draws += 1
            else: losses += 1
            
    return {
        "PJ": played, "G": wins, "E": draws, "P": losses,
        "GF": int(gf), "GC": int(ga),
        "Media GF": gf/played, "Media GC": ga/played
    }

def prepare_player_tables(df_players, team_name):
    real_team = fuzzy_match_team(team_name, df_players)
    df_p = df_players[df_players['team'] == real_team].copy()
    if df_p.empty: return None, None
    
    # Últimos 5 partidos del equipo para ver forma
    dates = sorted(df_p['date'].unique(), reverse=True)[:5]
    df_recent = df_p[df_p['date'].isin(dates)]
    
    if df_recent.empty: return None, None
    
    # Tablas
    sh = df_recent.groupby('player')[['sh','sot']].mean().sort_values('sh', ascending=False).head(6)
    fl = df_recent.groupby('player')[['fls','crdy']].mean().sort_values('fls', ascending=False).head(6)
    
    return sh.rename(columns={'sh':'Tiros','sot':'Puerta'}), fl.rename(columns={'fls':'Faltas','crdy':'Tarj'})

# --- INTERFAZ PRINCIPAL ---
full_df = load_all_matches()
df_players = load_players()

st.sidebar.title("🤖 Analista Total")

if full_df.empty:
    st.error("⚠️ Carpeta 'datos/' vacía o ilegible. Sube los CSVs a GitHub.")
else:
    # Selector Global de Equipos (Para que sirva de ayuda)
    all_teams = sorted(full_df[full_df['Date'] > '2025-08-01']['HomeTeam'].unique())
    if not all_teams: # Fallback si no hay partidos nuevos aun
        all_teams = sorted(full_df['HomeTeam'].unique())

    # --- PESTAÑAS ---
    tabs = st.tabs(["🆚 Comparador Total", "🛡️ Ficha Equipo", "⚽ Jugador", "🏟️ Plantilla"])

    # ==============================================================================
    # TAB 1: COMPARADOR TOTAL (Actual + Histórico)
    # ==============================================================================
    with tabs[0]:
        st.header("🆚 Comparador de Partidos")
        
        c1, c2 = st.columns(2)
        local = c1.selectbox("Local", all_teams, index=0)
        visitante = c2.selectbox("Visitante", all_teams, index=1)
        
        if st.button("📊 ANALIZAR ENFRENTAMIENTO", type="primary"):
            
            # 1. FORMA ACTUAL (25/26)
            s_loc = get_stats_pack_current(full_df, local, 'Home')
            s_vis = get_stats_pack_current(full_df, visitante, 'Away')
            
            # 2. JUGADORES (Forma)
            sh_loc, fl_loc = prepare_player_tables(df_players, local)
            sh_vis, fl_vis = prepare_player_tables(df_players, visitante)
            
            # 3. HISTÓRICO H2H (Desde 2004)
            h2h_df = get_h2h_history(full_df, local, visitante)
            
            # 4. NOTICIAS
            with st.spinner("Noticias..."):
                try: news = news_engine.get_live_context(local, visitante)
                except: news = {}

            st.divider()
            
            # --- ZONA 1: ACTUALIDAD ---
            st.subheader("🔥 Forma Actual (Temporada 25/26)")
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown(f"🏠 **{local} (En Casa)**")
                if s_loc:
                    st.write(f"Goles: {s_loc['goals']:.2f} | Córners: {s_loc['corners']:.2f}")
                    for l in s_loc['match_log']: st.caption(l)
                    if sh_loc is not None: 
                        st.dataframe(sh_loc.style.format("{:.2f}"), use_container_width=True)
                else: st.info("Sin datos recientes.")
                
            with col_b:
                st.markdown(f"✈️ **{visitante} (Fuera)**")
                if s_vis:
                    st.write(f"Goles: {s_vis['goals']:.2f} | Córners: {s_vis['corners']:.2f}")
                    for l in s_vis['match_log']: st.caption(l)
                    if sh_vis is not None: 
                        st.dataframe(sh_vis.style.format("{:.2f}"), use_container_width=True)
                else: st.info("Sin datos recientes.")

            st.divider()

            # --- ZONA 2: HISTÓRICO ---
            st.subheader("📚 Histórico Enfrentamientos (Desde 2004)")
            if h2h_df is not None:
                st.dataframe(h2h_df, hide_index=True, use_container_width=True)
            else:
                st.info("No hay enfrentamientos previos registrados.")
                
            with st.expander("📰 Ver Noticias"):
                st.write(news.get('texto', 'Sin noticias.'))

    # ==============================================================================
    # TAB 2: FICHA DE EQUIPO (Solo estadísticas propias)
    # ==============================================================================
    with tabs[1]:
        st.header("🛡️ Estadísticas Generales del Equipo")
        team_sel = st.selectbox("Selecciona Equipo", all_teams, key="t2_team")
        
        stats = get_team_general_stats(full_df, team_sel)
        
        if stats:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Jugados", stats['PJ'])
            c2.metric("Ganados", stats['G'])
            c3.metric("Goles Favor", stats['GF'])
            c4.metric("Goles Contra", stats['GC'])
            
            st.info(f"Promedio Goles a Favor: {stats['Media GF']:.2f} | Promedio Goles en Contra: {stats['Media GC']:.2f}")
            
            # Últimos partidos (General)
            last_games = get_stats_pack_current(full_df, team_sel, 'All')
            if last_games:
                st.write("**Últimos 5 partidos (General):**")
                for l in last_games['match_log']: st.text(l)
        else:
            st.warning("Sin datos esta temporada.")

    # ==============================================================================
    # TAB 3: JUGADOR (Buscador individual)
    # ==============================================================================
    with tabs[2]:
        st.header("⚽ Buscador de Jugadores")
        if not df_players.empty:
            teams_p = sorted(df_players['team'].dropna().unique()) if 'team' in df_players.columns else []
            t_p = st.selectbox("Equipo", teams_p, key="t3_t")
            
            pl_list = sorted(df_players[df_players['team']==t_p]['player'].unique())
            pl = st.selectbox("Jugador", pl_list, key="t3_p")
            
            p_data = df_players[df_players['player']==pl].sort_values('date', ascending=False)
            
            m1, m2 = st.columns(2)
            m1.metric("Media Tiros", f"{p_data['sh'].mean():.2f}")
            m2.metric("Media Faltas", f"{p_data['fls'].mean():.2f}")
            
            st.dataframe(p_data[['date','game','sh','sot','fls','crdy']].rename(columns=PLAYER_DICT), hide_index=True)
        else:
            st.warning("No hay datos de jugadores.")

    # ==============================================================================
    # TAB 4: PLANTILLA (Tabla completa)
    # ==============================================================================
    with tabs[3]:
        st.header("🏟️ Plantilla Completa")
        if not df_players.empty:
            t_sq = st.selectbox("Equipo", teams_p, key="t4_t")
            
            df_sq = df_players[df_players['team']==t_sq]
            # Agrupar por jugador
            summ = df_sq.groupby('player').agg({
                'date':'count', 'min':'sum', 'gls':'sum', 'ast':'sum',
                'sh':'mean', 'sot':'mean', 'fls':'mean', 'crdy':'sum'
            }).reset_index()
            
            st.dataframe(
                summ.rename(columns=PLAYER_DICT).style.format("{:.2f}", subset=['Remates','A Puerta','Faltas']),
                hide_index=True, use_container_width=True, height=600
            )

