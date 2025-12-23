import streamlit as st
import pandas as pd
import data_updater
import news_engine
from pathlib import Path

# Configuración
st.set_page_config(page_title="Analista Pro IA", layout="wide", page_icon="⚽")

# --- FUNCIONES DE CARGA ---
@st.cache_resource
def run_updater():
    data_updater.update_data()

@st.cache_data
def load_data():
    """Carga datos de partidos (Resultados)"""
    files = list(Path("datos").glob("*.csv"))
    league_files = [f for f in files if "jugadores" not in f.name]
    if not league_files: 
        return None
    
    df_list = []
    for f in league_files:
        try:
            temp_df = pd.read_csv(f)
            if 'Date' in temp_df.columns:
                temp_df['Date'] = pd.to_datetime(temp_df['Date'], dayfirst=True, errors='coerce')
            df_list.append(temp_df)
        except Exception as e:
            print(f"Error al cargar {f}: {e}")
            continue
    return pd.concat(df_list, ignore_index=True) if df_list else None

@st.cache_data
def load_player_data():
    """Carga datos de jugadores manejando errores"""
    path = Path("datos/jugadores_raw.csv")
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        # Normalizar fecha si existe
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        print(f"Error al cargar datos de jugadores: {e}")
        return None

def analyze_player_opportunities(df_players, market_type, line, min_matches, min_success_rate):
    """Analiza los jugadores según los filtros proporcionados."""
    results = []
    
    # Verificar si df_players es None o está vacío
    if df_players is None or df_players.empty:
        return pd.DataFrame()
        
    # Verificar columnas requeridas
    required_columns = ['player', 'team', 'date', 'sh', 'sot', 'fls', 'crdy']
    if not all(col in df_players.columns for col in required_columns):
        print(f"Faltan columnas requeridas. Columnas disponibles: {df_players.columns.tolist()}")
        return pd.DataFrame()
    
    for (player, team), group in df_players.groupby(['player', 'team']):
        last_matches = group.sort_values('date', ascending=False).head(min_matches)
        
        if len(last_matches) < min_matches:
            continue
            
        if market_type == 'Tiros Totales':
            metric_col = 'sh'
        elif market_type == 'Tiros a Puerta':
            metric_col = 'sot'
        elif market_type == 'Faltas Cometidas':
            metric_col = 'fls'
        elif market_type == 'Tarjetas Amarillas':
            metric_col = 'crdy'
        else:
            return pd.DataFrame()
            
        success = (last_matches[metric_col] > line).sum()
        success_rate = (success / min_matches) * 100
        avg_value = last_matches[metric_col].mean()
        
        last_5 = last_matches.head(5)
        last_5_results = []
        
        for _, match in last_5.iterrows():
            if match[metric_col] > line:
                last_5_results.append('✅')
            else:
                last_5_results.append('❌')
        
        while len(last_5_results) < 5:
            last_5_results.append('-')
            
        if success_rate >= min_success_rate:
            results.append({
                'Jugador': player,
                'Equipo': team,
                '% Acierto': f"{success_rate:.1f}%",
                f'Media {market_type}': f"{avg_value:.2f}",
                'Últimos 5': ' '.join(last_5_results)
            })
    
    return pd.DataFrame(results).sort_values('% Acierto', ascending=False)

def render_player_props_tab(df_players):
    """Renderiza la pestaña de análisis de jugadores."""
    st.header("⚽ Player Props")
    
    if df_players is None or df_players.empty:
        st.warning("No hay datos de jugadores disponibles. Asegúrate de tener el archivo 'jugadores_raw.csv' en la carpeta 'datos/'")
        return
    
    # Mostrar selector de equipo
    teams = sorted(df_players['team'].dropna().unique().tolist())
    selected_team = st.selectbox("Seleccionar Equipo", teams)
    
    # Filtrar jugadores por equipo
    team_players = df_players[df_players['team'] == selected_team]
    players = sorted(team_players['player'].unique().tolist())
    
    if not players:
        st.warning("No hay jugadores disponibles para este equipo.")
        return
    
    # Mostrar selector de jugador
    selected_player = st.selectbox("Seleccionar Jugador", players)
    
    # Mostrar estadísticas del jugador
    player_stats = df_players[df_players['player'] == selected_player].sort_values('date', ascending=False)
    
    if not player_stats.empty:
        st.subheader(f"📊 Estadísticas de {selected_player}")
        
        # Mostrar últimas 5 actuaciones
        st.write("### Últimos 5 partidos:")
        last_5 = player_stats.head(5)[['date', 'team', 'sh', 'sot', 'fls', 'crdy']]
        st.dataframe(last_5, use_container_width=True)
        
        # Mostrar promedios
        st.write("### Promedios (últimos 10 partidos):")
        last_10 = player_stats.head(10)
        if not last_10.empty:
            avg_sh = last_10['sh'].mean()
            avg_sot = last_10['sot'].mean()
            avg_fls = last_10['fls'].mean()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Tiros por partido", f"{avg_sh:.1f}")
            with col2:
                st.metric("Tiros a puerta por partido", f"{avg_sot:.1f}")
            with col3:
                st.metric("Faltas por partido", f"{avg_fls:.1f}")
    
    # Sección de búsqueda de oportunidades
    st.markdown("---")
    st.subheader("🔍 Buscar Oportunidades")
    
    col1, col2 = st.columns(2)
    
    with col1:
        market_type = st.selectbox(
            "Mercado",
            ["Tiros Totales", "Tiros a Puerta", "Faltas Cometidas", "Tarjetas Amarillas"]
        )
        line = st.number_input("Línea", min_value=0.5, max_value=10.0, step=0.5, value=1.5)
    
    with col2:
        min_matches = st.slider("Mínimo de partidos", 3, 20, 5)
        min_success = st.slider("% Mínimo de acierto", 50, 100, 70)
    
    if st.button("🔍 Buscar Oportunidades"):
        with st.spinner("Analizando jugadores..."):
            opportunities = analyze_player_opportunities(
                df_players, market_type, line, min_matches, min_success
            )
            
            if not opportunities.empty:
                st.success(f"✅ Se encontraron {len(opportunities)} oportunidades")
                st.dataframe(opportunities, use_container_width=True)
            else:
                st.warning("No se encontraron oportunidades que cumplan los criterios.")

def render_ia_tab(df):
    """Renderiza la pestaña de análisis con IA."""
    st.header("🧠 Inteligencia Artificial: Contexto Real")
    st.markdown("Esta herramienta cruza **Estadística Fría** con **Noticias de Última Hora**.")
    
    if df is None or df.empty:
        st.warning("No hay datos de partidos disponibles.")
        return
    
    col_a, col_b = st.columns(2)
    
    # Selectores de Partido
    todos_equipos = sorted(df['HomeTeam'].dropna().unique().tolist())
    
    with col_a:
        local = st.selectbox("Equipo Local", todos_equipos, index=0, key="ctx_home")
    with col_b:
        # Filtrar equipos visitantes para excluir el local
        visitantes = [t for t in todos_equipos if t != local]
        visitante = st.selectbox("Equipo Visitante", visitantes, index=0, key="ctx_away")
    
    # BOTÓN DE ESCANEO
    if st.button("📡 ESCANEAR ÚLTIMA HORA (INTERNET)", type="primary"):
        with st.spinner("Analizando datos..."):
            # 1. Obtener Datos Duros (Del CSV)
            stats_local = df[df['HomeTeam'] == local].tail(10)
            avg_goles_local = round(stats_local['FTHG'].mean(), 2) if not stats_local.empty else 0
            
            # 2. Obtener Contexto (Internet)
            with st.status("🕵️ Leyendo prensa deportiva y alineaciones...", expanded=True) as status:
                try:
                    contexto = news_engine.get_live_context(local, visitante)
                    status.update(label="✅ Análisis completado", state="complete", expanded=False)
                except Exception as e:
                    st.error(f"Error al obtener el contexto: {str(e)}")
                    contexto = {"error": f"Error al obtener el contexto: {str(e)}"}
            
            # 3. Mostrar Resultados
            st.divider()
            c1, c2 = st.columns([1, 1])
            
            with c1:
                st.subheader("📊 Datos Duros")
                st.info(f"Promedio Goles Local ({local}): {avg_goles_local}")
                st.write("**Historial H2H reciente:**")
                h2h = df[((df['HomeTeam']==local) & (df['AwayTeam']==visitante)) | 
                         ((df['HomeTeam']==visitante) & (df['AwayTeam']==local))].tail(5)
                if not h2h.empty:
                    st.dataframe(h2h[['Date', 'HomeTeam', 'AwayTeam', 'FTR']], 
                                hide_index=True, use_container_width=True)
                else:
                    st.info("No hay historial reciente entre estos equipos.")

            with c2:
                st.subheader("📰 Noticias Detectadas")
                if "error" in contexto:
                    st.warning(contexto["error"])
                else:
                    st.success(f"Fuentes leídas: {len(contexto.get('fuentes', []))}")
                    st.text_area("Extracto de Noticias:", 
                               value=contexto.get('texto', 'No hay noticias relevantes'), 
                               height=200)

            # 4. EL GENERADOR DE PROMPT
            st.divider()
            st.subheader("🤖 Tu Prompt para ChatGPT / Gemini")
            st.caption("Copia esto y pégalo en tu chat de IA favorito para obtener la predicción final.")
            
            prompt_final = f"""
ACTÚA COMO EL MEJOR ANALISTA DE APUESTAS DEPORTIVAS DEL MUNDO.

ESTOY ANALIZANDO EL PARTIDO: {local} vs {visitante}.

1. MIS DATOS ESTADÍSTICOS (CSV):
- El {local} promedia {avg_goles_local} goles en casa últimamente.
- Historial reciente: {len(h2h) if not h2h.empty else 'Sin'} enfrentamientos directos cargados.

2. CONTEXTO DE ÚLTIMA HORA (NOTICIAS/ALINEACIONES):
{contexto.get('texto', 'No hay noticias relevantes')}

TAREA:
Analiza críticamente cómo las noticias de última hora (lesiones, alineaciones) afectan a las estadísticas frías.
¿Hay alguna baja clave que cambie la probabilidad?
DAME:
1. Un pronóstico de resultado (1X2).
2. Una apuesta de valor (Over/Under o Ambos Marcan).
3. Un Player Prop si detectas oportunidad por bajas rivales.
"""
            st.text_area("COPIAR:", value=prompt_final.strip(), height=300)

def main():
    # Inicializar datos
    run_updater()
    df = load_data()
    df_players = load_player_data()
    
    # Barra lateral
    st.sidebar.title("🤖 Analista IA 2.0")
    
    # Pestañas
    tabs = st.tabs([
        "📊 Buscador Patrones", 
        "💎 Scanner Valor", 
        "🔮 Predicciones Stats", 
        "⚽ Player Props", 
        "📰 Contexto y Predicción IA"
    ])
    
    # Contenido de las pestañas
    with tabs[3]:  # Player Props
        render_player_props_tab(df_players)
    
    with tabs[4]:  # Contexto y Predicción IA
        render_ia_tab(df)
    
    # Nota sobre las otras pestañas
    with tabs[0]:
        st.info("🔍 Esta funcionalidad estará disponible en una próxima actualización.")
    with tabs[1]:
        st.info("💎 Esta funcionalidad estará disponible en una próxima actualización.")
    with tabs[2]:
        st.info("🔮 Esta funcionalidad estará disponible en una próxima actualización.")

if __name__ == "__main__":
    main()
