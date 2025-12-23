import requests
from pathlib import Path
import time

def update_data():
    # Configuración de temporadas (desde 0405 hasta 2526)
    current_season = "2526"
    seasons = []
    # Generamos códigos: 0405, 0506 ... 2526
    for year in range(4, 26): 
        start = f"{year:02d}"
        end = f"{year+1:02d}"
        seasons.append(f"{start}{end}")
    
    leagues = ['SP1', 'SP2'] # 1ª y 2ª División
    data_dir = Path("datos")
    data_dir.mkdir(exist_ok=True)
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"📚 Verificando Base de Datos Histórica (2004 - 2026)...")
    
    for season in seasons:
        for league in leagues:
            filename = f"{league}_{season}.csv"
            filepath = data_dir / filename
            
            # URL de football-data.co.uk
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            
            # Lógica inteligente:
            # 1. Si es la temporada actual (2526), descargar SIEMPRE (para tener los partidos de ayer).
            # 2. Si es una temporada vieja y NO tenemos el archivo, descargar.
            # 3. Si es vieja y YA lo tenemos, saltar.
            if season != current_season and filepath.exists():
                continue
                
            try:
                print(f"⬇️ Descargando: {filename}...")
                r = requests.get(url, headers=headers)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
                else:
                    print(f"   ❌ No encontrado (Posiblemente aún no existe): {season}")
                time.sleep(0.5) # Pausa para no saturar su servidor
            except Exception as e:
                print(f"⚠️ Error en {filename}: {e}")

    print("\n✅ Base de datos actualizada.")

if __name__ == "__main__":
    update_data()
