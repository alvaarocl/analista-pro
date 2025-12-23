import soccerdata as sd
import pandas as pd
from pathlib import Path
import warnings
import unicodedata

warnings.filterwarnings('ignore')

# Mapeo para normalizar nombres de equipos
TEAM_MAP = {
    "betis": "Real Betis", "real betis": "Real Betis",
    "athletic": "Athletic Club", "ath bilbao": "Athletic Club",
    "rayo": "Rayo Vallecano", "alaves": "Alavés",
    "cadiz": "Cádiz", "girona": "Girona",
    "real madrid": "Real Madrid", "barcelona": "Barcelona",
    "atletico madrid": "Ath Madrid", "sevilla": "Sevilla",
    "valencia": "Valencia", "real sociedad": "Real Sociedad",
    "getafe": "Getafe", "mallorca": "Mallorca",
    "osasuna": "Osasuna", "villareal": "Villarreal",
    "villarreal": "Villarreal", "celta": "Celta", "celta vigo": "Celta",
    "palmas": "Las Palmas", "las palmas": "Las Palmas",
    "leganes": "Leganés", "valladolid": "Real Valladolid", "espanyol": "Espanyol"
}

def normalize_name(name):
    if not isinstance(name, str): return str(name)
    n = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return n.lower().strip()

def fix_game_column(df, df_name):
    """
    Busca la columna del ID del partido (game, game_id, match_id)
    y la renombra obligatoriamente a 'game'.
    """
    if df.empty:
        return df

    # Limpiar nombres de columnas primero
    df.columns = [str(c[-1] if isinstance(c, tuple) else c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.contains('unnamed')]

    # Posibles nombres que usa soccerdata
    candidates = ['game', 'game_id', 'match_id', 'match']
    
    found_col = None
    for col in candidates:
        if col in df.columns:
            found_col = col
            break
            
    if found_col:
        # Si se llama distinto a 'game', renombramos
        if found_col != 'game':
            print(f"🔧 Arreglando columna en {df_name}: '{found_col}' -> 'game'")
            df = df.rename(columns={found_col: 'game'})
    else:
        print(f"⚠️ ADVERTENCIA: No encuentro la columna 'game' en {df_name}. Columnas disponibles: {list(df.columns)}")
        # Intentamos adivinar si alguna columna parece un ID (contiene números o hashes)
        # Esto es un fallback de emergencia
    
    return df

def download_player_stats():
    print("📥 Iniciando descarga de JUGADORES (Temporada 25/26)...")
    
    try:
        # IMPORTANTE: Usamos la temporada 2526
        fbref = sd.FBref(leagues="ESP-La Liga", seasons=["2526"])
        
        print("📅 Descargando Calendario...")
        schedule = fbref.read_schedule().reset_index()
        schedule = fix_game_column(schedule, "Calendario")
        
        # Filtramos solo lo necesario del calendario
        if 'game' in schedule.columns and 'date' in schedule.columns:
            schedule_min = schedule[['game', 'date']].drop_duplicates()
        else:
            print("❌ Error: El calendario no tiene 'game' o 'date'.")
            return

        print("⚽ Descargando Estadísticas (Summary)...")
        summary = fbref.read_player_match_stats(stat_type="summary").reset_index()
        summary = fix_game_column(summary, "Stats Summary")

        print("🟨 Descargando Estadísticas (Misc)...")
        misc = fbref.read_player_match_stats(stat_type="misc").reset_index()
        misc = fix_game_column(misc, "Stats Misc")

        # Verificar si tenemos datos
        if summary.empty:
            print("❌ Error: No se han encontrado datos de jugadores (Summary vacío).")
            return

        print("🔄 Procesando y uniendo tablas...")
        
        # Claves de unión seguras
        join_keys = ['game', 'team', 'player']
        
        # Verificar que existen las claves en ambos
        missing_summ = [k for k in join_keys if k not in summary.columns]
        missing_misc = [k for k in join_keys if k in misc.columns] # Misc a veces no trae todo, ajustamos
        
        if missing_summ:
            print(f"❌ Faltan columnas clave en Summary: {missing_summ}")
            return

        # Unión Summary + Misc
        df = pd.merge(summary, misc, on=join_keys, how='left', suffixes=('', '_misc'))
        
        # Unión con Fechas
        df = pd.merge(df, schedule_min, on='game', how='left')
        
        # --- LIMPIEZA DE DUPLICADOS ---
        # Borra filas si un jugador sale repetido en el mismo partido
        initial_rows = len(df)
        df = df.drop_duplicates(subset=['game', 'player'])
        final_rows = len(df)
        if initial_rows > final_rows:
            print(f"🧹 Se eliminaron {initial_rows - final_rows} filas duplicadas.")

        # Normalizar nombres de equipos
        if 'team' in df.columns:
            df['team'] = df['team'].apply(lambda x: TEAM_MAP.get(normalize_name(x), x))

        # Rellenar ceros en métricas clave
        cols_to_numeric = ['sh', 'sot', 'fls', 'crdy', 'gls', 'ast']
        for col in cols_to_numeric:
            if col not in df.columns: df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Guardar
        out_path = Path("datos/jugadores_raw.csv")
        out_path.parent.mkdir(exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"✅ ¡ÉXITO! Base de datos generada en: {out_path}")
        print(f"📊 Total registros: {len(df)}")

    except Exception as e:
        import traceback
        print(f"❌ Error Crítico: {e}")
        print(traceback.format_exc()) # Esto nos dirá la línea exacta si vuelve a fallar

if __name__ == "__main__":
    download_player_stats()
