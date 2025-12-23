"""
Motor de Jugadores - FBref Downloader (Temporada 25/26)
"""
import soccerdata as sd
import pandas as pd
from pathlib import Path
import warnings
import unicodedata

warnings.filterwarnings('ignore')

# Mapeo para normalizar nombres
TEAM_MAP = {
    "betis": "Real Betis",
    "real betis": "Real Betis",
    "athletic": "Athletic Club",
    "ath bilbao": "Athletic Club",
    "rayo": "Rayo Vallecano",
    "alaves": "Alavés",
    "cadiz": "Cádiz",
    "atlético madrid": "Atletico Madrid",
    "atletico madrid": "Atletico Madrid",
    "girona": "Girona",
    "real madrid": "Real Madrid",
    "barcelona": "Barcelona"
}

def normalize_name(name):
    if not isinstance(name, str): return str(name)
    n = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return n.lower().strip()

def clean_columns(df):
    new_cols = []
    for col in df.columns:
        if isinstance(col, tuple):
            c = col[-1] if col[-1] else col[0]
            new_cols.append(str(c).lower().strip())
        else:
            new_cols.append(str(col).lower().strip())
    df.columns = new_cols
    return df.loc[:, ~df.columns.str.contains('unnamed')]

def download_player_stats():
    print("📥 Descargando JUGADORES Temporada 25/26 (FBref)...")
    
    try:
        # CAMBIO CLAVE: Solo temporada "2526"
        fbref = sd.FBref(leagues="ESP-La Liga", seasons=["2526"])
        
        print("📅 Descargando Calendario...")
        schedule = fbref.read_schedule().reset_index()
        schedule = clean_columns(schedule)
        
        id_col = 'game_id' if 'game_id' in schedule.columns else 'game'
        if 'date' not in schedule.columns:
            print("⚠️ Error: Falta columna fecha")
            return

        schedule_min = schedule[[id_col, 'date']].drop_duplicates()

        print("⚽ Descargando Stats...")
        summary = fbref.read_player_match_stats(stat_type="summary").reset_index()
        misc = fbref.read_player_match_stats(stat_type="misc").reset_index()
        
        summary = clean_columns(summary)
        misc = clean_columns(misc)

        print("🔄 Procesando...")
        join_keys = ['game', 'team', 'player']
        join_keys = [k for k in join_keys if k in summary.columns]
        
        misc_cols = [c for c in ['fls', 'fld', 'crdy', 'crdr'] if c in misc.columns]
        misc_clean = misc[join_keys + misc_cols]
        
        df = pd.merge(summary, misc_clean, on=join_keys, how='left')
        df = pd.merge(df, schedule_min, left_on='game', right_on=id_col, how='left')
        
        if 'team' in df.columns:
            df['team'] = df['team'].apply(lambda x: TEAM_MAP.get(normalize_name(x), x))

        for col in ['sh', 'sot', 'fls', 'crdy', 'gls', 'ast']:
            if col not in df.columns: df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        out_path = Path("datos/jugadores_raw.csv")
        out_path.parent.mkdir(exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"✅ Guardado datos 25/26 en {out_path} ({len(df)} filas)")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    download_player_stats()
