import soccerdata as sd
import pandas as pd
from pathlib import Path
import warnings
import unicodedata

warnings.filterwarnings('ignore')

def normalize_name(name):
    if not isinstance(name, str): return str(name)
    n = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return n.lower().strip()

# Mapeo de equipos (FBref -> FootballData)
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
    "palmas": "Las Palmas", "las palmas": "Las Palmas"
}

def download_player_stats():
    print("📥 Descargando JUGADORES 25/26 (Esto tarda unos minutos)...")
    try:
        fbref = sd.FBref(leagues="ESP-La Liga", seasons=["2526"])
        
        schedule = fbref.read_schedule().reset_index()
        schedule.columns = [str(c[-1] if isinstance(c, tuple) else c).lower() for c in schedule.columns]
        
        # ID de partido y fecha
        id_col = 'game_id' if 'game_id' in schedule.columns else 'game'
        schedule_min = schedule[[id_col, 'date']].drop_duplicates()

        summary = fbref.read_player_match_stats(stat_type="summary").reset_index()
        misc = fbref.read_player_match_stats(stat_type="misc").reset_index()
        
        # Limpieza de columnas MultiIndex
        for df in [summary, misc]:
            df.columns = [str(c[-1] if isinstance(c, tuple) else c).lower() for c in df.columns]
            # Eliminar columnas duplicadas o 'unnamed'
            df = df.loc[:, ~df.columns.str.contains('unnamed')]

        # Unión
        df = pd.merge(summary, misc, on=['game', 'team', 'player'], how='left', suffixes=('', '_misc'))
        df = pd.merge(df, schedule_min, left_on='game', right_on=id_col, how='left')
        
        # Normalizar nombres de equipos
        if 'team' in df.columns:
            df['team'] = df['team'].apply(lambda x: TEAM_MAP.get(normalize_name(x), x))

        # Asegurar numéricos
        for col in ['sh', 'sot', 'fls', 'crdy', 'gls', 'ast']:
            if col not in df.columns: df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        out = Path("datos/jugadores_raw.csv")
        out.parent.mkdir(exist_ok=True)
        df.to_csv(out, index=False)
        print(f"✅ ÉXITO: {out} generado con {len(df)} filas.")

    except Exception as e:
        print(f"❌ Error crítico: {e}")

if __name__ == "__main__":
    download_player_stats()
