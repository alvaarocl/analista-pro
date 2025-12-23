import streamlit as st
import pandas as pd
from pathlib import Path
import unicodedata
import os

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Analista Pro 25/26", layout="wide", page_icon="⚽")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .win { color: #4CAF50; font-weight: bold; font-size: 1.5em; padding: 0 5px; }
    .loss { color: #F44336; font-weight: bold; font-size: 1.5em; padding: 0 5px; }
    .draw { color: #FFC107; font-weight: bold; font-size: 1.5em; padding: 0 5px; }
    .big-metric { font-size: 26px; font-weight: bold; color: #f0f2f6; }
    .sub-metric { font-size: 14px; color: #9ca3af; }
    /* Ajuste para que los selectores se vean bien */
    div[data-baseweb="select"] > div { background-color: #262730; }
</style>
""", unsafe_allow_html=True)

# --- DICCIONARIOS Y MAPEOS ---
TEAM_MAPPING = {
    "Alaves": "Alavés", "Ath Bilbao": "Athletic Club", "Ath Madrid": "Atlético Madrid",
    "Atletico Madrid": "Atlético Madrid", "Barcelona": "Barcelona", "Betis": "Real Betis",
    "Cadiz": "Cádiz", "Celta": "Celta Vigo", "Espanol": "Espanyol", "Getafe": "Getafe",
    "Girona": "Girona", "Granada": "Granada", "Las Palmas": "Las Palmas",
    "Mallorca": "Mallorca", "Osasuna": "Osasuna", "Rayo Vallecano": "Rayo Vallecano",
    "Real Madrid": "Real Madrid", "Real Sociedad": "Real Sociedad", "Sevilla": "Sevilla",
    "Valencia": "Valencia", "Valladolid": "Real Valladolid", "Villarreal": "Villarreal",
    "Almeria": "Almería", "Leganes": "Leganés", "Racing Santander": "Racing Santander",
    "Levante": "Levante", "Eibar": "Eibar", "Burgos": "Burgos", "Sporting Gijon": "Sporting Gijón",
    "Oviedo": "Real Oviedo", "Huesca": "Huesca", "Zaragoza": "Real Zaragoza", "Elche": "Elche",
    "Tenerife": "Tenerife", "Albacete": "Albacete", "Cartagena": "Cartagena", "Mirandes": "Mirandés"
}

# --- CARGA DE DATOS ---
def get_data_dir():
    if Path("DATOS").exists(): return Path("DATOS")
    elif Path("datos").exists(): return Path("datos")
    return None

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
            
            # Asegurar columnas necesarias
            for col in ['Div', 'HS','AS','HST','AST','HC','AC','HF','AF','HY','AY']:
                if col not in d.columns: 
                    if col == 'Div': d[col] = 'SP1' # Asumir primera si falta
                    else: d[col] = 0
            
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
            df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

# --- UTILIDADES ---
def normalize_str(s):
    if not isinstance(s, str): return str(s)
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')

def fuzzy_match_team(team_name, df_players):
    if team_name is None: return None
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

def generate_streak_html(results):
    html = ""
    for r in results:
        if r == '✅': color = 'win'
        elif r == '❌': color = 'loss'
        else: color = 'draw'
        html += f"<span class='{color}'>{r}</span> "
    return html

def get_advanced_form(df, team, games=5, filter_mode='Auto'):
    if df.empty or team is None: return None
    
    # Usar datos desde Agosto 2024 para la temporada actual
    df_curr = df.sort_values('Date', ascending=True)
    
    if filter_mode == 'Home': matches = df_curr[df_curr['HomeTeam'] == team]
    elif filter_mode == 'Away': matches = df_curr[df_curr['AwayTeam'] == team]
    else: matches = df_curr[(df_curr['HomeTeam'] == team) | (df_curr['AwayTeam'] == team)]
    
    matches = matches.sort_values('Date', ascending=True).tail(games)
    
    if matches.empty: return None
    
    stats = {'gf': [], 'ga': [], 'sh': [], 'sot': [], 'corn': [], 'card': [], 'foul': [], 'res': []}
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
            
        res = '✅' if gf > ga else ('❌' if gf < ga else '➖')
        
        stats['gf'].append(gf); stats['ga'].append(ga)
        stats['sh'].append(sh); stats['sot'].append(sot)
        stats['corn'].append(co); stats['card'].append(ca); stats['foul'].append(fo)
        stats['res'].append(res)
        log.append(f"{d_str} {res} {int(gf)}-{int(ga)} vs {opp} {tag}")

    c = len(matches)
    return {
        'gf': sum(stats['gf'])/c, 'ga': sum(stats['ga'])/c,
        'sh': sum(stats['sh'])/c, 'sot': sum(stats['sot'])/c,
        'corn': sum(stats['corn'])/c, 'card': sum(stats['card'])/c, 
        'foul': sum(stats['foul'])/c, 'log': log, 'raw_results': stats['res']
    }

def get_player_rankings(df_players, team_name):
    real_team = fuzzy_match_team(team_name, df_players)
    if not real_team: return None, None, None
    
    df_p = df_players[df_players['team'] == real_team].copy()
    if df_p.empty: return None, None, None
    
    for col in ['gls', 'ast', 'min', 'sh', 'sot', 'fls', 'crdy']:
        if col in df_p.columns: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)

    scorers = df_p.groupby('player')[['gls', 'ast', 'min']].sum().sort_values('gls', ascending=False).head(5)
    
    # Filtro mínimo partidos para medias
    gc = df_p['player'].value_counts()
    valid = gc[gc >= 2].index
    df_val = df_p[df_p['player'].isin(valid)]
    
    shooters = df_val.groupby('player')[['sh', 'sot']].mean().sort_values('sh', ascending=False).head(5)
    bad_boys = df_val.groupby('player')[['fls', 'crdy']].mean().sort_values('fls', ascending=False).head(5)
    
    return scorers, shooters, bad_boys

def get_h2h_history(df, t1, t2):
    if t1 is None or t2 is None: return None
    mask = ((df['HomeTeam'] == t1) & (df['AwayTeam'] == t2)) | ((df['HomeTeam'] == t2) & (df['AwayTeam'] == t1))
    h2h = df[mask].sort_values('Date', ascending=False)
    if h2h.empty: return None
    
    data = []
    for _, r in h2h.iterrows():
        data.append({
            "Fecha": r['Date'].strftime("%d/%m/%Y"), "Local": r['HomeTeam'],
            "Res": f"{int(r['FTHG'])}-{int(r['FTAG'])}", "Visitante": r['AwayTeam'],
            "1": r.get('B365H', '-'), "X": r.get('B365D', '-'), "2": r.get('B365A', '-')
        })
    return pd.DataFrame(data)

# --- NUEVO COMPONENTE: SELECTOR DE EQUIPOS UNIVERSAL ---
def render_team_selector(df_matches, key_suffix, label="Equipo"):
    """
    Renderiza un selector con filtro de 1ª/2ª División.
    Devuelve el equipo seleccionado o None.
    """
    # Clasificar equipos por división basándonos en los últimos partidos jugados
    # Cogemos datos de la temporada actual (desde Agosto 2025)
    df_recent = df_matches[df_matches['Date'] > '2025-08-01']
    if df_recent.empty:
        # Fallback si no hay datos recientes, usamos todo
        df_recent = df_matches

    # Equipos que han jugado en SP1 (1ª) y SP2 (2ª) recientemente
    teams_sp1 = sorted(df_recent[df_recent['Div'] == 'SP1']['HomeTeam'].unique())
    teams_sp2 = sorted(df_recent[df_recent['Div'] == 'SP2']['HomeTeam'].unique())
    
    # Si las listas están vacías (porque data_updater no bajó SP2, por ejemplo), rellenar
    if not teams_sp1: teams_sp1 = sorted(df_matches['HomeTeam'].unique())
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        division = st.radio(f"División ({label})", ["1ª División", "2ª División"], horizontal=True, key=f"div_{key_suffix}")
    
    with col2:
        lista_equipos = teams_sp1 if division == "1ª División" else teams_sp2
        # index=None hace que empiece vacío
        selected_team = st.selectbox(f"Selecciona {label}", lista_equipos, index=None, placeholder="Buscar equipo...", key=f"sel_{key_suffix}")
        
    return selected_team

# --- INTERFAZ PRINCIPAL ---
full_df = load_all_matches()
df_players = load_players()

# SIDEBAR DIAGNOSTICO (Mínimo)
st.sidebar.title("Analista Pro")
if full_df.empty:
    st.sidebar.error("⚠️ No hay datos. Ejecuta los scripts en tu PC.")
else:
    st.sidebar.success("✅ Base de datos cargada.")

tabs = st.tabs(["🆚 Comparador", "🛡️ Ficha Equipo", "⚽ Ficha Jugador", "🏟️ Plantilla"])

# ==============================================================================
# TAB 1: COMPARADOR (DOBLE SELECTOR)
# ==============================================================================
with tabs[0]:
    st.header("🆚 Comparador de Partidos")
    
    # Contenedor para los selectores
    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            local = render_team_selector(full_df, "loc", "Local")
        with c2:
            visitante = render_team_selector(full_df, "vis", "Visitante")
            
    st.divider()

    if local and visitante:
        n_games = st.slider("Analizar últimos X partidos", 5, 20, 5)
        
        # Lógica de Análisis
        stats_loc = get_advanced_form(full_df, local, n_games, "Home")
        stats_vis = get_advanced_form(full_df, visitante, n_games, "Away")
        
        if stats_loc and stats_vis:
            st.subheader(f"📊 {local} (Casa) vs {visitante} (Fuera)")
            
            c_r1, c_r2 = st.columns(2)
            with c_r1: 
                st.markdown(f"**Racha {local}:** {generate_streak_html(stats_loc['raw_results'])}", unsafe_allow_html=True)
            with c_r2:
                st.markdown(f"**Racha {visitante}:** {generate_streak_html(stats_vis['raw_results'])}", unsafe_allow_html=True)

            # Tabla comparativa
            comp_data = {
                "Métrica": ["Goles A/C", "Tiros Tot/Puer", "Córners", "Tarjetas", "Faltas"],
                f"{local}": [
                    f"{stats_loc['gf']:.1f} / {stats_loc['ga']:.1f}", 
                    f"{stats_loc['sh']:.1f} / {stats_loc['sot']:.1f}", 
                    f"{stats_loc['corn']:.1f}", f"{stats_loc['card']:.1f}", f"{stats_loc['foul']:.1f}"
                ],
                f"{visitante}": [
                    f"{stats_vis['gf']:.1f} / {stats_vis['ga']:.1f}", 
                    f"{stats_vis['sh']:.1f} / {stats_vis['sot']:.1f}", 
                    f"{stats_vis['corn']:.1f}", f"{stats_vis['card']:.1f}", f"{stats_vis['foul']:.1f}"
                ]
            }
            st.dataframe(pd.DataFrame(comp_data), hide_index=True, use_container_width=True)

            st.divider()
            
            # Jugadores
            st.subheader("🔥 Jugadores Clave (25/26)")
            scorers_L, shooters_L, cards_L = get_player_rankings(df_players, local)
            scorers_V, shooters_V, cards_V = get_player_rankings(df_players, visitante)
            
            cp1, cp2 = st.columns(2)
            with cp1:
                st.markdown(f"**{local}**")
                if scorers_L is not None:
                    st.caption("Goleadores"); st.dataframe(scorers_L[['gls','ast']], use_container_width=True)
                    st.caption("Faltas/Amarillas"); st.dataframe(cards_L[['fls','crdy']].style.format("{:.1f}"), use_container_width=True)
                else: st.info("Sin datos jugadores.")
            with cp2:
                st.markdown(f"**{visitante}**")
                if scorers_V is not None:
                    st.caption("Goleadores"); st.dataframe(scorers_V[['gls','ast']], use_container_width=True)
                    st.caption("Faltas/Amarillas"); st.dataframe(cards_V[['fls','crdy']].style.format("{:.1f}"), use_container_width=True)
                else: st.info("Sin datos jugadores.")

            # H2H
            st.divider()
            h2h = get_h2h_history(full_df, local, visitante)
            with st.expander("📚 Historial H2H"):
                if h2h is not None: st.dataframe(h2h, hide_index=True, use_container_width=True)
                else: st.write("Sin enfrentamientos previos.")
                
    else:
        st.info("👈 Selecciona los equipos arriba para ver la comparativa.")

# ==============================================================================
# TAB 2: FICHA EQUIPO
# ==============================================================================
with tabs[1]:
    st.header("🛡️ Ficha de Equipo")
    team_sel = render_team_selector(full_df, "tab2", "Equipo")
    
    if team_sel:
        stats = get_advanced_form(full_df, team_sel, 20, 'General')
        if stats:
            st.markdown(f"### 📊 Rendimiento: {team_sel}")
            st.caption("Medias últimos 20 partidos")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Goles Favor", f"{stats['gf']:.2f}")
            col2.metric("Tiros/Part", f"{stats['sh']:.2f}")
            col3.metric("Córners", f"{stats['corn']:.2f}")
            col4.metric("Faltas", f"{stats['foul']:.2f}")
            
            st.markdown(f"<div style='text-align:center; padding:10px;'>{generate_streak_html(stats['raw_results'])}</div>", unsafe_allow_html=True)
            
            st.write("**Historial Reciente:**")
            for l in stats['log'][::-1][:10]: st.text(l)
    else:
        st.info("Selecciona un equipo para ver sus estadísticas.")

# ==============================================================================
# TAB 3: JUGADOR
# ==============================================================================
with tabs[2]:
    st.header("⚽ Buscador de Jugador")
    
    # 1. Seleccionar Equipo
    team_p = render_team_selector(full_df, "tab3", "Equipo del Jugador")
    
    if team_p:
        # 2. Seleccionar Jugador (filtrado por equipo)
        real_team = fuzzy_match_team(team_p, df_players)
        if real_team:
            players = sorted(df_players[df_players['team'] == real_team]['player'].unique())
            player_sel = st.selectbox("Selecciona Jugador", players, index=None)
            
            if player_sel:
                p_stats = df_players[df_players['player'] == player_sel].sort_values('date', ascending=False)
                st.subheader(f"👤 {player_sel}")
                
                # Métricas totales
                tot_g = p_stats['gls'].sum()
                tot_a = p_stats['ast'].sum()
                media_sh = p_stats['sh'].mean()
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Goles Totales", int(tot_g))
                m2.metric("Asistencias", int(tot_a))
                m3.metric("Tiros/Partido", f"{media_sh:.2f}")
                
                st.dataframe(p_stats[['date','game','min','gls','ast','sh','sot','fls','crdy']], hide_index=True, use_container_width=True)
        else:
            st.warning("No hay datos de jugadores para este equipo.")
    else:
        st.info("Primero selecciona el equipo del jugador.")

# ==============================================================================
# TAB 4: PLANTILLA
# ==============================================================================
with tabs[3]:
    st.header("🏟️ Plantilla Completa")
    team_sq = render_team_selector(full_df, "tab4", "Equipo")
    
    if team_sq:
        real_team = fuzzy_match_team(team_sq, df_players)
        if real_team:
            df_sq = df_players[df_players['team'] == real_team]
            summ = df_sq.groupby('player').agg({
                'min':'sum', 'gls':'sum', 'ast':'sum', 
                'sh':'mean', 'sot':'mean', 'fls':'mean', 'crdy':'sum'
            }).reset_index()
            
            st.dataframe(
                summ.rename(columns={'min':'Min','gls':'G','ast':'A','sh':'Tiros/P','sot':'Puerta/P','fls':'Faltas/P','crdy':'Amarillas'})
                .style.format("{:.2f}", subset=['Tiros/P','Puerta/P','Faltas/P']),
                hide_index=True, use_container_width=True, height=700
            )
        else:
            st.warning("No hay datos de plantilla disponible.")
    else:
        st.info("Selecciona un equipo para ver su plantilla.")
