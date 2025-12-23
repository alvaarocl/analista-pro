"""
Módulo de Actualización Automática de Datos (Partidos)
Descarga archivos CSV de football-data.co.uk
"""
import requests
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

def update_data():
    urls = {
        'SP1': 'https://www.football-data.co.uk/mmz4281/2425/SP1.csv', # 1ª División
        'SP2': 'https://www.football-data.co.uk/mmz4281/2425/SP2.csv'  # 2ª División
    }
    
    data_dir = Path("datos")
    data_dir.mkdir(exist_ok=True)
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print("--- Actualizando Datos de Partidos ---")
    for league, url in urls.items():
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                file_path = data_dir / f"{league}.csv"
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Descargado: {league}.csv")
            else:
                print(f"❌ Error {response.status_code} en {league}")
        except Exception as e:
            print(f"⚠️ Error descargando {league}: {e}")

if __name__ == "__main__":
    update_data()
