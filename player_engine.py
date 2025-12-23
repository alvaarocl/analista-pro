import soccerdata as sd
import pandas as pd
from pathlib import Path
import warnings
import unicodedata

warnings.filterwarnings('ignore')

# Mapeo de equipos
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

def flatten_and_clean(df, source_name):
    """
    Aplana MultiIndex, saca el índice a columnas y renombra lo básico.
    """
    print(f"🔧 Procesando tabla: {source_name}...")
    
    # 1. Aplanar columnas MultiIndex (Ej: ('Performance', 'Gls') -> 'gls')
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
            # Cogemos el último nivel que no esté vacío
            # Si col es ('', 'Player') -> 'Player'
            # Si col es ('Performance', 'Gls') -> 'Gls'
            c_name = col[-1] if col[-1] else (col[0] if col[0] else "unknown")
            new_cols.append(str(c_name))
        df.columns = new_cols

    # 2. Resetear el índice (Aquí es donde suelen estar 'game', 'player', 'team')
    # soccerdata suele poner los IDs en el índice, no en las columnas.
    df = df.reset_index()

    # 3. Limpieza de nombres
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 4. Renombrado inteligente (si el índice no tenía nombre, se llama 'level_0', etc)
    # soccerdata devuelve: league, season, game, team, player (en ese orden en el índice)
    
    # Mapeo explícito de columnas conocidas
    rename_map = {
        'game_id': 'game', 'match_id': 'game', 'match': 'game',
        'squad': 'team', 'opponent': 'opponent', 
        'player': 'player', 'date': 'date'
    }
    df = df.rename(columns=rename_map)

    # 5. Eliminar columnas vacías o 'unnamed'
    df = df.loc[:, ~df.columns.str.contains('unnamed')]
    df = df.loc[:, df.columns != '']

    # Debug: Ver si tenemos lo necesario
    required = ['game', 'team', 'player']
    missing = [x for x in required if x not in df.columns]
    
    if missing:
        print(f"⚠️ AVISO en {source_name}: Faltan columnas {missing}. Columnas actuales: {list(df.columns)}")
    else:
        print(f"✅ {source_name} procesada correctamente.")
        
    return df

def download_player_stats():
    print("📥 Iniciando descarga de JUGADORES 25/26 (Script Robusto)...")
    
    try:
        # Usamos temporada 2526
        fbref = sd.FBref(leagues="ESP-La Liga", seasons=["2526"])
        
        # 1. CALENDARIO
        print("📅 Descargando Calendario...")
        schedule = fbref.read_schedule()
        schedule = flatten_and_clean(schedule, "Calendario")
        
        if 'game' in schedule.columns and 'date' in schedule.columns:
            schedule_min = schedule[['game', 'date']].drop_duplicates()
        else:
            print("❌ Error crítico: No se pudo extraer 'game' y 'date' del calendario.")
            return

        # 2. SUMMARY (Estadísticas principales)
        print("⚽ Descargando Stats Summary...")
        summary = fbref.read_player_match_stats(stat_type="summary")
        summary = flatten_and_clean(summary, "Summary")

        # 3. MISC (Tarjetas, faltas, etc)
        print("🟨 Descargando Stats Misc...")
        misc = fbref.read_player_match_stats(stat_type="misc")
        misc = flatten_and_clean(misc, "Misc")

        # 4. UNIÓN
        print("🔄 Uniendo tablas...")
        
        # Aseguramos claves de unión
        join_keys = ['game', 'team', 'player']
        
        # Verificar integridad
        if not set(join_keys).issubset(summary.columns):
            print("❌ Deteniendo: Faltan claves en Summary.")
            return

        # Merge Summary + Misc
        df = pd.merge(summary, misc, on=join_keys, how='left', suffixes=('', '_misc'))
        
        # Merge con Fechas
        df = pd.merge(df, schedule_min, on='game', how='left')
        
        # 5. LIMPIEZA FINAL
        # Eliminar duplicados
        initial = len(df)
        df = df.drop_duplicates(subset=['game', 'player'])
        final = len(df)
        if initial > final:
            print(f"🧹 Eliminados {initial - final} registros duplicados.")

        # Normalizar equipos
        if 'team' in df.columns:
            df['team'] = df['team'].apply(lambda x: TEAM_MAP.get(normalize_name(x), x))

        # Convertir a números (rellenar vacíos con 0)
        numeric_cols = ['sh', 'sot', 'fls', 'crdy', 'gls', 'ast']
        for col in numeric_cols:
            if col not in df.columns: df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 6. GUARDAR
        out_path = Path("datos/jugadores_raw.csv")
        out_path.parent.mkdir(exist_ok=True)
        df.to_csv(out_path, index=False)
        
        print(f"✅ ¡ÉXITO! Base de datos generada en: {out_path}")
        print(f"📊 Filas totales: {len(df)}")
        print("👉 AHORA: Sube 'datos/jugadores_raw.csv' a GitHub.")

    except Exception as e:
        import traceback
        print(f"❌ ERROR CRÍTICO DEL SISTEMA: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    download_player_stats()
