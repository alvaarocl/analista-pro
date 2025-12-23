import streamlit as st
import pandas as pd
import data_updater
import news_engine
import player_engine  # Importamos esto para poder descargar datos si faltan
from pathlib import Path
import unicodedata

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analista Pro (Solo Datos)", layout="wide", page_icon="⚽")

# --- DICCIONARIOS ---
PLAYER_DICT = {
    "player": "Jugador", "team": "Equipo", "date": "Fecha",
    "sh": "Remates", "sot": "A Puerta", "fls": "Faltas", 
    "crdy": "T. Amarillas", "gls": "Goles", "ast": "Asistencias",
    "min": "Minutos", "game_count": "PJ"
}

MATCH_DICT = {
    "Date": "Fecha", "HomeTeam": "Local", "AwayTeam": "Visitante",
    "FTHG": "Goles Loc", "FTAG": "Goles Vis", "HS": "Tiros Loc", "AS": "Tiros Vis",
    "HST": "Puerta Loc", "AST": "Puerta Vis", "HY": "Amarillas Loc", "AY": "Amarillas Vis",
    "HC": "Corners Loc", "AC": "Corners Vis"
}

# --- CARGA DE DATOS ---
@st.cache_resource
def run_updates():
    """Descarga datos al iniciar si no existen o para actualizar"""
    # 1. Actualizar partidos
    data_updater.update_data()
    
    # 2. Verificar si existen los jugadores. Si no, descargarlos AHORA.
    # Esto es vital para Streamlit Cloud donde el disco empieza vacío.
    players_path = Path("datos/jugadores_raw.csv")
    if not players_path.exists():
        with st.spinner("⚠️ Descargando base de datos de jugadores por primera vez (puede tardar 1 min)..."):
            player_engine.download_player_stats()

@st.cache_data
def load_matches():
    files = list(Path("datos").glob("*.csv"))
    files = [f for f in files if "jugadores" not in f.name]
    dfs = []
    for f in files:
        try:
            d = pd.read_csv(f)
            if 'Date' in d.columns:
                d['Date'] = pd.to_datetime(d['Date'], dayfirst=True, errors='coerce')
            dfs.append(d)
        except: continue
    if not dfs: return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

@st.cache_data
def load_players():
    path = Path("datos/jugadores_raw.csv")
    if not path.exists(): return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        # Normalizar columnas a minúsculas y sin espacios
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # CORRECCIÓN DE ERROR KEYERROR:
        # A veces FBref llama a la columna 'squad' en lugar de 'team'. Lo unificamos.
        if 'squad' in df.columns:
            df = df.rename(columns={'squad': 'team'})
            
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
        return df
    except: return pd.DataFrame()

# --- FUNCIONES LÓGICAS ---

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

def get_stats_pack(df, team, venue_filter='All'):
    """Calcula stats y devuelve también el historial de rivales."""
    if df.empty: return None
    
    if venue_filter == 'Home': matches = df[df['HomeTeam'] == team]
    elif venue_filter == 'Away': matches = df[df['AwayTeam'] == team]
    else: matches = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)]
        
    matches = matches.sort_values('Date').tail(5)
    if matches.empty: return None
    
    stats = {'goals': [], 'shots': [], 'corners': [], 'cards': [], 'fouls': []}
    history = [] 

    for _, r in matches.iterrows():
        is_home = (r['HomeTeam'] == team)
        opponent = r['AwayTeam'] if is_home else r['HomeTeam']
        
        if is_home:
            hg, ag = r['FTHG'], r['FTAG']
            res = '✅' if hg > ag else ('❌' if hg < ag else '➖')
            stats['goals'].append(hg); stats['shots'].append(r.get('HS', 0))
            stats['corners'].append(r.get('HC', 0)); stats['cards'].append(r.get('HY', 0))
            stats['fouls'].append(r.get('HF', 0))
            history.append(f"{res} {int(hg)}-{int(ag)} vs {opponent} (C)")
        else:
            hg, ag = r['FTHG'], r['FTAG']
            res = '✅' if ag > hg else ('❌' if ag < hg else '➖')
            stats['goals'].append(ag); stats['shots'].append(r.get('AS', 0))
            stats['corners'].append(r.get('AC', 0)); stats['cards'].append(r.get('AY', 0))
            stats['fouls'].append(r.get('AF', 0))
            history.append(f"{res} {int(ag)}-{int(hg)} vs {opponent} (F)")

    avgs = {k: sum(v)/len(v) if v else 0 for k, v in stats.items()}
    avgs['count'] = len(matches)
    avgs['match_log'] = history 
    return avgs

def get_extended_player_list(df_players, team_name):
    """Devuelve DataFrames de jugadores clave."""
    # PROTECCIÓN CONTRA EL ERROR KEYERROR
    if df_players.empty or 'team' not in df_players.columns:
        return pd.DataFrame()
        
    real_team = fuzzy_match_team(team_name, df_players)
    df_p = df_players[df_players['team'] == real_team].copy()
    if df_p.empty: return pd.DataFrame()
    
    recent_dates = sorted(df_p['date'].unique(), reverse=True)[:5]
    df_recent = df_p[df_p['date'].isin(recent_dates)]
    return df_recent

def prepare_display_tables(df_recent):
    """Prepara las tablas bonitas (Top 6)"""
    if df_recent is None or df_recent.empty: return None, None
    
    # Tabla 1: Rematadores
    df_sh = df_recent.groupby('player')[['sh', 'sot']].mean().sort_values('sh', ascending=False).head(6)
    df_sh = df_sh.rename(columns={'sh': 'Remates', 'sot': 'A Puerta'})
    
    # Tabla 2: Leñeros
    df_fls = df_recent.groupby('player')[['fls', 'crdy']].mean().sort_values('fls', ascending=False).head(6)
    df_fls = df_fls.rename(columns={'fls': 'Faltas', 'crdy': 'Tarjetas'})
    
    return df_sh, df_fls

# --- INTERFAZ ---
# Ejecutamos la actualización al principio
run_updates()

df = load_matches()
df_players = load_players()

st.sidebar.title("🤖 Analista Pro")
tabs = st.tabs(["📉 Comparador de Datos", "📊 Base de Datos", "⚽ Jugador", "🏟️ Plantillas"])

# ==============================================================================
# TAB 1: COMPARADOR DE DATOS (SOLO DATOS)
# ==============================================================================
with tabs[0]:
    st.header("📉 Comparador de Datos Puro")
    
    if df.empty:
        st.warning("⚠️ No se encontraron datos de partidos. Verifica que la descarga funcionó.")
    else:
        teams = sorted(df['HomeTeam'].dropna().unique())
        c1, c2 = st.columns(2)
        local = c1.selectbox("Local", teams, index=0)
        visitante = c2.selectbox("Visitante", teams, index=1)
        
        if st.button("📊 MOSTRAR DATOS", type="primary"):
            
            # 1. OBTENER DATOS
            spec_loc = get_stats_pack(df, local, 'Home')
            spec_vis = get_stats_pack(df, visitante, 'Away')
            
            # Datos Jugadores
            df_p_loc = get_extended_player_list(df_players, local)
            df_p_vis = get_extended_player_list(df_players, visitante)
            
            # Noticias
            with st.spinner("Cargando noticias..."):
                try:
                    news = news_engine.get_live_context(local, visitante)
                except:
                    news = {}

            st.divider()

            # --- SECCIÓN 1: HISTORIAL ---
            st.subheader("🗓️ Historial Reciente (Contexto de Fuerza)")
            
            col_h1, col_h2 = st.columns(2)
            
            with col_h1:
                st.markdown(f"**{local} (Últimos 5 en Casa)**")
                if spec_loc:
                    for match in spec_loc['match_log']:
                        st.text(match)
                else:
                    st.info("Sin partidos en casa recientes.")
            
            with col_h2:
                st.markdown(f"**{visitante} (Últimos 5 Fuera)**")
                if spec_vis:
                    for match in spec_vis['match_log']:
                        st.text(match)
                else:
                    st.info("Sin partidos fuera recientes.")

            st.divider()

            # --- SECCIÓN 2: COMPARATIVA NUMÉRICA ---
            st.subheader("⚖️ Estadísticas Medias (Casa vs Fuera)")
            
            if spec_loc and spec_vis:
                comp_spec = {
                    "Métrica": ["Goles a Favor", "Tiros Totales", "Córners", "Tarjetas", "Faltas Cometidas"],
                    f"{local} (CASA)": [
                        f"{spec_loc['goals']:.2f}", f"{spec_loc['shots']:.2f}", f"{spec_loc['corners']:.2f}", 
                        f"{spec_loc['cards']:.2f}", f"{spec_loc['fouls']:.2f}"
                    ],
                    f"{visitante} (FUERA)": [
                        f"{spec_vis['goals']:.2f}", f"{spec_vis['shots']:.2f}", f"{spec_vis['corners']:.2f}", 
                        f"{spec_vis['cards']:.2f}", f"{spec_vis['fouls']:.2f}"
                    ]
                }
                st.dataframe(pd.DataFrame(comp_spec), hide_index=True, use_container_width=True)
            else:
                st.warning("Faltan datos para la comparativa numérica.")

            st.divider()

            # --- SECCIÓN 3: JUGADORES CLAVE ---
            st.subheader("🔥 Rendimiento Individual (Media Últimos 5)")
            
            col_pl_loc, col_pl_vis = st.columns(2)
            
            # LOCAL
            with col_pl_loc:
                st.markdown(f"🏠 **{local}**")
                if not df_p_loc.empty:
                    sh_loc, fl_loc = prepare_display_tables(df_p_loc)
                    if sh_loc is not None:
                        st.caption("🎯 Francotiradores (Tiros)")
                        st.dataframe(sh_loc.style.format("{:.2f}"), use_container_width=True)
                        st.caption("🪓 Leñeros (Faltas/Tarjetas)")
                        st.dataframe(fl_loc.style.format("{:.2f}"), use_container_width=True)
                else:
                    st.info(f"Sin datos de jugadores para {local}.")

            # VISITANTE
            with col_pl_vis:
                st.markdown(f"✈️ **{visitante}**")
                if not df_p_vis.empty:
                    sh_vis, fl_vis = prepare_display_tables(df_p_vis)
                    if sh_vis is not None:
                        st.caption("🎯 Francotiradores (Tiros)")
                        st.dataframe(sh_vis.style.format("{:.2f}"), use_container_width=True)
                        st.caption("🪓 Leñeros (Faltas/Tarjetas)")
                        st.dataframe(fl_vis.style.format("{:.2f}"), use_container_width=True)
                else:
                    st.info(f"Sin datos de jugadores para {visitante}.")

            with st.expander("📰 Ver Noticias de Prensa (Bajas y Contexto)"):
                st.write(news.get('texto', 'Sin noticias disponibles.'))

# ==============================================================================
# TABS RESTANTES
# ==============================================================================
with tabs[1]:
    st.header("📊 Base de Datos")
    if not df.empty:
        tm = st.selectbox("Equipo", ["Todos"]+sorted(df['HomeTeam'].unique()))
        show = df if tm=="Todos" else df[(df['HomeTeam']==tm)|(df['AwayTeam']==tm)]
        st.dataframe(show.tail(20).rename(columns=MATCH_DICT), hide_index=True, use_container_width=True)

with tabs[2]:
    st.header("⚽ Jugador")
    if not df_players.empty:
        teams = sorted(df_players['team'].dropna().unique()) if 'team' in df_players.columns else []
        if teams:
            tm = st.selectbox("Equipo", teams, key="t2_tm")
            pl = st.selectbox("Jugador", sorted(df_players[df_players['team']==tm]['player'].unique()), key="t2_pl")
            stats = df_players[df_players['player']==pl].sort_values('date', ascending=False)
            st.dataframe(stats[['date','game','sh','sot','fls','crdy']].rename(columns=PLAYER_DICT), hide_index=True)
        else:
            st.warning("Datos de jugadores incompletos.")

with tabs[3]:
    st.header("🏟️ Plantilla")
    if not df_players.empty:
        teams = sorted(df_players['team'].dropna().unique()) if 'team' in df_players.columns else []
        if teams:
            tm = st.selectbox("Equipo", teams, key="t3_tm")
            df_t = df_players[df_players['team']==tm]
            summ = df_t.groupby('player').agg({'sh':'mean','sot':'mean','fls':'mean','crdy':'sum'}).sort_values('sh', ascending=False).reset_index()
            summ = summ.rename(columns={'date': 'game_count'})
            st.dataframe(summ.rename(columns=PLAYER_DICT).style.format({"Remates": "{:.2f}", "A Puerta": "{:.2f}", "Faltas": "{:.2f}"}), hide_index=True, use_container_width=True, height=600)
