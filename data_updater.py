"""
Módulo de Actualización: TEMPORADA 25/26 (ACTUAL)
"""
import requests
from pathlib import Path

def update_data():
    # URLs actualizadas a la temporada 25/26
    urls = {
        'SP1': 'https://www.football-data.co.uk/mmz4281/2526/SP1.csv', # 1ª División 25/26
        'SP2': 'https://www.football-data.co.uk/mmz4281/2526/SP2.csv'  # 2ª División 25/26
    }
    
    data_dir = Path("datos")
    data_dir.mkdir(exist_ok=True)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print("--- Descargando Temporada 2025/2026 ---")
    for league, url in urls.items():
        try:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                with open(data_dir / f"{league}.csv", 'wb') as f:
                    f.write(r.content)
                print(f"✅ {league}.csv actualizado (Temporada 25/26)")
            else:
                print(f"❌ Error descargando {league}: {r.status_code} (Quizás la temporada no ha empezado o URL incorrecta)")
        except Exception as e:
            print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    update_data()
