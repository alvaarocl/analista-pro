"""
Data Processor para Análisis de Fútbol
Procesa archivos CSV de football-data.co.uk y calcula métricas de forma reciente
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
import warnings

warnings.filterwarnings('ignore')


class FootballDataProcessor:
    """
    Clase para procesar datos de fútbol y calcular métricas de forma reciente.
    Evita data leakage usando shift(1) para basar las estadísticas solo en partidos anteriores.
    """
    
    def __init__(self, data_dir: str = "DATOS"):
        """
        Inicializa el procesador de datos.
        
        Args:
            data_dir: Directorio que contiene los archivos CSV
        """
        self.data_dir = Path(data_dir)
        self.df: Optional[pd.DataFrame] = None
        
    def load_and_concat_data(self) -> pd.DataFrame:
        """
        Carga y concatena todos los archivos CSV de la carpeta datos/.
        Asegura que las columnas de cuotas de Bet365 estén presentes.
        
        Returns:
            DataFrame con todos los datos concatenados
        """
        csv_files = list(self.data_dir.glob("*.csv"))
        
        if not csv_files:
            raise FileNotFoundError(f"No se encontraron archivos CSV en {self.data_dir}")
        
        dataframes = []
        
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file, encoding='utf-8')
                # Agregar columna de temporada si no existe
                if 'Season' not in df.columns:
                    df['Season'] = csv_file.stem
                dataframes.append(df)
                print(f"✓ Cargado: {csv_file.name} ({len(df)} partidos)")
            except Exception as e:
                print(f"⚠ Error al cargar {csv_file.name}: {e}")
                continue
        
        if not dataframes:
            raise ValueError("No se pudieron cargar archivos CSV")
        
        combined_df = pd.concat(dataframes, ignore_index=True)
        print(f"\n✓ Total de partidos cargados: {len(combined_df)}")
        
        # Verificar y crear columnas de cuotas si no existen
        combined_df = self._ensure_odds_columns(combined_df)
        
        return combined_df
    
    def _ensure_odds_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Asegura que existan las columnas de cuotas de Bet365.
        Si no existen, las simula con valores aleatorios para pruebas.
        
        Args:
            df: DataFrame con los datos
            
        Returns:
            DataFrame con columnas de cuotas aseguradas
        """
        df = df.copy()
        
        # Columnas de cuotas requeridas
        odds_columns = {
            'B365H': 'B365H',  # Cuota victoria local
            'B365D': 'B365D',  # Cuota empate
            'B365A': 'B365A',  # Cuota victoria visitante
            'B365>2.5': 'B365>2.5',  # Cuota más de 2.5 goles
            'B365<2.5': 'B365<2.5'   # Cuota menos de 2.5 goles
        }
        
        # Buscar variaciones de nombres de columnas
        available_cols = df.columns.tolist()
        
        # Mapear columnas disponibles
        for standard_name, possible_names in [
            ('B365H', ['B365H', 'B365H', 'BWH', 'WHH']),
            ('B365D', ['B365D', 'BWD', 'WHD']),
            ('B365A', ['B365A', 'BWA', 'WHA']),
            ('B365>2.5', ['B365>2.5', 'B365>2.5', 'P>2.5', 'Avg>2.5']),
            ('B365<2.5', ['B365<2.5', 'B365<2.5', 'P<2.5', 'Avg<2.5'])
        ]:
            found = False
            for possible in possible_names:
                if possible in available_cols:
                    if standard_name != possible:
                        df[standard_name] = df[possible]
                    found = True
                    break
            
            if not found:
                # Simular cuotas aleatorias si no existen
                print(f"⚠ Columna {standard_name} no encontrada. Simulando cuotas aleatorias...")
                if standard_name == 'B365H':
                    # Cuotas de victoria local: típicamente entre 1.2 y 8.0
                    df[standard_name] = np.random.uniform(1.2, 8.0, len(df))
                elif standard_name == 'B365D':
                    # Cuotas de empate: típicamente entre 2.5 y 5.0
                    df[standard_name] = np.random.uniform(2.5, 5.0, len(df))
                elif standard_name == 'B365A':
                    # Cuotas de victoria visitante: típicamente entre 1.2 y 8.0
                    df[standard_name] = np.random.uniform(1.2, 8.0, len(df))
                elif standard_name == 'B365>2.5':
                    # Cuotas más de 2.5 goles: típicamente entre 1.5 y 2.5
                    df[standard_name] = np.random.uniform(1.5, 2.5, len(df))
                elif standard_name == 'B365<2.5':
                    # Cuotas menos de 2.5 goles: típicamente entre 1.3 y 2.0
                    df[standard_name] = np.random.uniform(1.3, 2.0, len(df))
        
        return df
    
    def convert_date_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convierte la columna 'Date' a datetime.
        Maneja formatos dd/mm/yy y dd/mm/yyyy.
        
        Args:
            df: DataFrame con columna Date
            
        Returns:
            DataFrame con Date convertida a datetime
        """
        df = df.copy()
        
        if 'Date' not in df.columns:
            raise ValueError("La columna 'Date' no existe en el DataFrame")
        
        # Intentar diferentes formatos de fecha
        date_formats = ['%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%d-%m-%Y']
        
        for fmt in date_formats:
            try:
                df['Date'] = pd.to_datetime(df['Date'], format=fmt, errors='coerce')
                # Si la mayoría de fechas se convirtieron correctamente, usar este formato
                if df['Date'].notna().sum() / len(df) > 0.8:
                    break
            except:
                continue
        
        # Si aún hay valores nulos, intentar conversión automática
        if df['Date'].isna().any():
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
        
        # Eliminar filas con fechas inválidas
        invalid_dates = df['Date'].isna().sum()
        if invalid_dates > 0:
            print(f"⚠ Se eliminaron {invalid_dates} filas con fechas inválidas")
            df = df.dropna(subset=['Date'])
        
        # Ordenar por fecha
        df = df.sort_values('Date').reset_index(drop=True)
        
        return df
    
    def calculate_rolling_metrics(self, df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
        """
        Calcula métricas de forma reciente (rolling mean) para equipos locales y visitantes.
        IMPORTANTE: Usa shift(1) para evitar data leakage.
        
        Métricas calculadas:
        - Goles a favor (FTHG/FTAG)
        - Tiros (HS/AS)
        - Tiros a puerta (HST/AST)
        - Faltas (HF/AF)
        - Corners (HC/AC)
        
        Args:
            df: DataFrame con los datos de partidos
            window: Ventana de partidos para el rolling mean (default: 5)
            
        Returns:
            DataFrame con las nuevas columnas de métricas agregadas
        """
        df = df.copy()
        
        # Columnas requeridas
        required_cols = ['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'Date']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Faltan columnas requeridas: {missing_cols}")
        
        # Columnas opcionales (si no existen, se crearán con valores NaN)
        optional_cols = ['HS', 'AS', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC']
        
        # Verificar y crear columnas faltantes
        for col in optional_cols:
            if col not in df.columns:
                df[col] = np.nan
                print(f"⚠ Columna {col} no encontrada. Se creará con valores NaN.")
        
        # Inicializar columnas de métricas
        metric_cols = [
            'Home_Rolling_Goals', 'Home_Rolling_Shots', 'Home_Rolling_ShotsOnTarget',
            'Home_Rolling_Fouls', 'Home_Rolling_Corners',
            'Away_Rolling_Goals', 'Away_Rolling_Shots', 'Away_Rolling_ShotsOnTarget',
            'Away_Rolling_Fouls', 'Away_Rolling_Corners'
        ]
        for col in metric_cols:
            df[col] = np.nan
        
        # Obtener todos los equipos únicos
        all_teams = set(df['HomeTeam'].unique()) | set(df['AwayTeam'].unique())
        
        print(f"\nCalculando métricas de forma reciente para {len(all_teams)} equipos...")
        
        # Crear índice temporal para mapear correctamente
        df['_original_index'] = df.index
        
        # Para cada equipo, calcular sus estadísticas históricas
        for team in all_teams:
            # Obtener todos los partidos del equipo (como local y visitante)
            home_mask = df['HomeTeam'] == team
            away_mask = df['AwayTeam'] == team
            
            home_indices = df[home_mask].index.tolist()
            away_indices = df[away_mask].index.tolist()
            
            # Obtener partidos ordenados por fecha
            home_matches = df.loc[home_indices].sort_values('Date').copy()
            away_matches = df.loc[away_indices].sort_values('Date').copy()
            
            # Calcular rolling metrics para partidos como local
            if len(home_matches) > 0:
                home_matches['_rolling_goals'] = home_matches['FTHG'].shift(1).rolling(window=window, min_periods=1).mean()
                home_matches['_rolling_shots'] = home_matches['HS'].shift(1).rolling(window=window, min_periods=1).mean()
                home_matches['_rolling_shots_on_target'] = home_matches['HST'].shift(1).rolling(window=window, min_periods=1).mean()
                home_matches['_rolling_fouls'] = home_matches['HF'].shift(1).rolling(window=window, min_periods=1).mean()
                home_matches['_rolling_corners'] = home_matches['HC'].shift(1).rolling(window=window, min_periods=1).mean()
                
                # Mapear de vuelta al DataFrame original usando los índices originales
                for _, row in home_matches.iterrows():
                    orig_idx = row['_original_index']
                    df.loc[orig_idx, 'Home_Rolling_Goals'] = row['_rolling_goals']
                    df.loc[orig_idx, 'Home_Rolling_Shots'] = row['_rolling_shots']
                    df.loc[orig_idx, 'Home_Rolling_ShotsOnTarget'] = row['_rolling_shots_on_target']
                    df.loc[orig_idx, 'Home_Rolling_Fouls'] = row['_rolling_fouls']
                    df.loc[orig_idx, 'Home_Rolling_Corners'] = row['_rolling_corners']
            
            # Calcular rolling metrics para partidos como visitante
            if len(away_matches) > 0:
                away_matches['_rolling_goals'] = away_matches['FTAG'].shift(1).rolling(window=window, min_periods=1).mean()
                away_matches['_rolling_shots'] = away_matches['AS'].shift(1).rolling(window=window, min_periods=1).mean()
                away_matches['_rolling_shots_on_target'] = away_matches['AST'].shift(1).rolling(window=window, min_periods=1).mean()
                away_matches['_rolling_fouls'] = away_matches['AF'].shift(1).rolling(window=window, min_periods=1).mean()
                away_matches['_rolling_corners'] = away_matches['AC'].shift(1).rolling(window=window, min_periods=1).mean()
                
                # Mapear de vuelta al DataFrame original usando los índices originales
                for _, row in away_matches.iterrows():
                    orig_idx = row['_original_index']
                    df.loc[orig_idx, 'Away_Rolling_Goals'] = row['_rolling_goals']
                    df.loc[orig_idx, 'Away_Rolling_Shots'] = row['_rolling_shots']
                    df.loc[orig_idx, 'Away_Rolling_ShotsOnTarget'] = row['_rolling_shots_on_target']
                    df.loc[orig_idx, 'Away_Rolling_Fouls'] = row['_rolling_fouls']
                    df.loc[orig_idx, 'Away_Rolling_Corners'] = row['_rolling_corners']
        
        # Limpiar columnas temporales
        df = df.drop(columns=['_original_index'], errors='ignore')
        
        print("✓ Métricas de forma reciente calculadas correctamente")
        
        return df
    
    def find_value_opportunities(self, min_sample_size: int = 30, min_accuracy: float = 0.60) -> pd.DataFrame:
        """
        Busca automáticamente patrones con valor esperado positivo.
        Itera sobre diferentes umbrales de estadísticas y calcula el EV.
        
        Args:
            min_sample_size: Tamaño mínimo de muestra (n) para considerar un patrón
            min_accuracy: Porcentaje mínimo de acierto (0.60 = 60%)
            
        Returns:
            DataFrame con oportunidades encontradas ordenadas por EV descendente
        """
        if self.df is None:
            raise ValueError("Debes ejecutar process_all() primero")
        
        df = self.df.copy()
        
        # Filtrar solo partidos con métricas válidas y cuotas
        required_cols = ['FTHG', 'FTAG', 'FTR', 'B365H', 'B365D', 'B365A', 'B365>2.5']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Faltan columnas requeridas: {missing_cols}")
        
        # Eliminar filas con valores nulos en columnas críticas
        df = df.dropna(subset=['FTHG', 'FTAG', 'Date'])
        
        opportunities = []
        
        # Definir umbrales a probar para diferentes métricas
        metric_thresholds = {
            'Home_Rolling_Goals': [0.5, 1.0, 1.5, 2.0, 2.5],
            'Home_Rolling_Shots': [8, 10, 12, 14, 16, 18],
            'Home_Rolling_ShotsOnTarget': [3, 4, 5, 6, 7],
            'Away_Rolling_Goals': [0.5, 1.0, 1.5, 2.0, 2.5],
            'Away_Rolling_Shots': [8, 10, 12, 14, 16, 18],
            'Away_Rolling_ShotsOnTarget': [3, 4, 5, 6, 7],
        }
        
        # Eventos a analizar
        events = [
            {
                'name': 'Victoria Local',
                'condition': lambda d: d['FTR'] == 'H',
                'odds_col': 'B365H'
            },
            {
                'name': 'Empate',
                'condition': lambda d: d['FTR'] == 'D',
                'odds_col': 'B365D'
            },
            {
                'name': 'Victoria Visitante',
                'condition': lambda d: d['FTR'] == 'A',
                'odds_col': 'B365A'
            },
            {
                'name': 'Más de 2.5 goles',
                'condition': lambda d: (d['FTHG'] + d['FTAG']) > 2.5,
                'odds_col': 'B365>2.5'
            },
            {
                'name': 'Menos de 2.5 goles',
                'condition': lambda d: (d['FTHG'] + d['FTAG']) < 2.5,
                'odds_col': 'B365<2.5'
            },
            {
                'name': 'Ambos equipos marcan',
                'condition': lambda d: (d['FTHG'] > 0) & (d['FTAG'] > 0),
                'odds_col': 'B365>2.5'  # Aproximación, usar cuota de más de 2.5 como proxy
            }
        ]
        
        print(f"\n🔍 Buscando oportunidades de valor...")
        print(f"   Muestra mínima: {min_sample_size} partidos")
        print(f"   Acierto mínimo: {min_accuracy*100:.0f}%")
        
        # Iterar sobre cada métrica y umbral
        for metric_col, thresholds in metric_thresholds.items():
            if metric_col not in df.columns:
                continue
            
            for threshold in thresholds:
                # Filtrar partidos que cumplen la condición
                filtered = df[df[metric_col] >= threshold].copy()
                
                if len(filtered) < min_sample_size:
                    continue
                
                # Probar cada evento
                for event in events:
                    odds_col = event['odds_col']
                    
                    if odds_col not in filtered.columns:
                        continue
                    
                    # Calcular resultados
                    try:
                        event_occurred = event['condition'](filtered)
                        n_matches = len(filtered)
                        n_success = event_occurred.sum()
                        
                        if n_matches < min_sample_size:
                            continue
                        
                        # Probabilidad real
                        real_probability = n_success / n_matches
                        
                        if real_probability < min_accuracy:
                            continue
                        
                        # Obtener cuotas válidas (eliminar NaN e infinitos)
                        valid_odds = filtered[odds_col].dropna()
                        valid_odds = valid_odds[np.isfinite(valid_odds)]
                        
                        if len(valid_odds) == 0:
                            continue
                        
                        # Filtrar cuotas razonables (entre 1.01 y 100)
                        valid_odds = valid_odds[(valid_odds >= 1.01) & (valid_odds <= 100)]
                        
                        if len(valid_odds) == 0:
                            continue
                        
                        avg_odds = valid_odds.mean()
                        
                        # Calcular EV: EV = (Probabilidad_Real * Cuota_Media) - 1
                        ev = (real_probability * avg_odds) - 1
                    except Exception as e:
                        # Continuar con el siguiente patrón si hay error
                        continue
                    
                    # Guardar oportunidad
                    opportunities.append({
                        'Patrón': f"{metric_col} >= {threshold}",
                        'Evento': event['name'],
                        'Muestra (n)': n_matches,
                        'Aciertos': n_success,
                        'Probabilidad Real': f"{real_probability*100:.2f}%",
                        'Cuota Media': f"{avg_odds:.2f}",
                        'EV': ev,
                        'EV %': f"{ev*100:.2f}%"
                    })
        
        # Crear DataFrame y ordenar por EV descendente
        if opportunities:
            opportunities_df = pd.DataFrame(opportunities)
            opportunities_df = opportunities_df.sort_values('EV', ascending=False)
            print(f"\n✓ Encontradas {len(opportunities_df)} oportunidades")
            return opportunities_df
        else:
            print("\n⚠ No se encontraron oportunidades que cumplan los criterios")
            return pd.DataFrame(columns=['Patrón', 'Evento', 'Muestra (n)', 'Aciertos', 
                                         'Probabilidad Real', 'Cuota Media', 'EV', 'EV %'])
    
    def get_team_current_stats(self, team_name: str, as_home: bool = True, last_n: int = 5) -> dict:
        """
        Obtiene las estadísticas actuales de un equipo basadas en sus últimos N partidos.
        
        Args:
            team_name: Nombre del equipo
            as_home: True para estadísticas como local, False para visitante
            last_n: Número de partidos a considerar
            
        Returns:
            Diccionario con las estadísticas actuales
        """
        if self.df is None:
            raise ValueError("Debes ejecutar process_all() primero")
        
        df = self.df.copy()
        
        # Filtrar partidos del equipo
        if as_home:
            team_matches = df[df['HomeTeam'] == team_name].copy()
            prefix = 'Home'
        else:
            team_matches = df[df['AwayTeam'] == team_name].copy()
            prefix = 'Away'
        
        if len(team_matches) == 0:
            return {}
        
        # Ordenar por fecha descendente y tomar últimos N
        team_matches = team_matches.sort_values('Date', ascending=False).head(last_n)
        
        if len(team_matches) == 0:
            return {}
        
        # Calcular promedios
        stats = {
            'Goles': team_matches[f'FTHG' if as_home else 'FTAG'].mean() if len(team_matches) > 0 else 0,
            'Tiros': team_matches[f'HS' if as_home else 'AS'].mean() if f'HS' in team_matches.columns else 0,
            'Tiros a Puerta': team_matches[f'HST' if as_home else 'AST'].mean() if f'HST' in team_matches.columns else 0,
            'Faltas': team_matches[f'HF' if as_home else 'AF'].mean() if f'HF' in team_matches.columns else 0,
            'Corners': team_matches[f'HC' if as_home else 'AC'].mean() if f'HC' in team_matches.columns else 0,
            'Partidos Analizados': len(team_matches)
        }
        
        return stats
    
    def match_patterns_with_current_stats(self, home_stats: dict, away_stats: dict, 
                                          value_patterns_df: pd.DataFrame) -> list:
        """
        Compara las estadísticas actuales de dos equipos con los patrones de valor encontrados.
        
        Args:
            home_stats: Estadísticas del equipo local
            away_stats: Estadísticas del equipo visitante
            value_patterns_df: DataFrame con patrones de valor (resultado de find_value_opportunities)
            
        Returns:
            Lista de coincidencias encontradas
        """
        matches = []
        
        if value_patterns_df is None or len(value_patterns_df) == 0:
            return matches
        
        # Mapeo de nombres de estadísticas a columnas del DataFrame
        stat_mapping = {
            'Goles': 'Rolling_Goals',
            'Tiros': 'Rolling_Shots',
            'Tiros a Puerta': 'Rolling_ShotsOnTarget',
            'Faltas': 'Rolling_Fouls',
            'Corners': 'Rolling_Corners'
        }
        
        # Mapeo inverso para buscar estadísticas en los diccionarios
        reverse_stat_mapping = {
            'Rolling_Goals': 'Goles',
            'Rolling_Shots': 'Tiros',
            'Rolling_ShotsOnTarget': 'Tiros a Puerta',
            'Rolling_Fouls': 'Faltas',
            'Rolling_Corners': 'Corners'
        }
        
        # Iterar sobre cada patrón de valor
        for _, pattern_row in value_patterns_df.iterrows():
            pattern_str = pattern_row['Patrón']
            event = pattern_row['Evento']
            ev = pattern_row['EV']
            
            # Solo considerar patrones con EV positivo
            if ev <= 0:
                continue
            
            # Extraer métrica y umbral del patrón
            # Formato esperado: "Home_Rolling_Goals >= 1.5" o "Away_Rolling_Shots >= 12"
            try:
                if 'Home_' in pattern_str:
                    metric_part = pattern_str.replace('Home_', '').split(' >= ')
                    if len(metric_part) == 2:
                        metric_name = metric_part[0]
                        threshold = float(metric_part[1])
                        
                        # Buscar estadística correspondiente en home_stats
                        stat_key = reverse_stat_mapping.get(metric_name)
                        if stat_key and stat_key in home_stats:
                            stat_value = home_stats[stat_key]
                            if stat_value >= threshold:
                                matches.append({
                                    'Tipo': 'Local',
                                    'Estadística': stat_key,
                                    'Valor Actual': stat_value,
                                    'Umbral Patrón': threshold,
                                    'Evento': event,
                                    'EV': ev,
                                    'EV %': pattern_row['EV %'],
                                    'Probabilidad Real': pattern_row['Probabilidad Real'],
                                    'Muestra Histórica': pattern_row['Muestra (n)']
                                })
                
                elif 'Away_' in pattern_str:
                    metric_part = pattern_str.replace('Away_', '').split(' >= ')
                    if len(metric_part) == 2:
                        metric_name = metric_part[0]
                        threshold = float(metric_part[1])
                        
                        # Buscar estadística correspondiente en away_stats
                        stat_key = reverse_stat_mapping.get(metric_name)
                        if stat_key and stat_key in away_stats:
                            stat_value = away_stats[stat_key]
                            if stat_value >= threshold:
                                matches.append({
                                    'Tipo': 'Visitante',
                                    'Estadística': stat_key,
                                    'Valor Actual': stat_value,
                                    'Umbral Patrón': threshold,
                                    'Evento': event,
                                    'EV': ev,
                                    'EV %': pattern_row['EV %'],
                                    'Probabilidad Real': pattern_row['Probabilidad Real'],
                                    'Muestra Histórica': pattern_row['Muestra (n)']
                                })
            except Exception as e:
                # Continuar con el siguiente patrón si hay error
                continue
        
        # Ordenar por EV descendente
        matches.sort(key=lambda x: x['EV'], reverse=True)
        
        return matches
    
    def process_all(self) -> pd.DataFrame:
        """
        Ejecuta todo el pipeline de procesamiento.
        
        Returns:
            DataFrame procesado con todas las métricas
        """
        print("=" * 60)
        print("PROCESAMIENTO DE DATOS DE FÚTBOL")
        print("=" * 60)
        
        # 1. Cargar y concatenar datos
        self.df = self.load_and_concat_data()
        
        # 2. Convertir fechas
        self.df = self.convert_date_column(self.df)
        
        # 3. Calcular métricas de forma reciente
        self.df = self.calculate_rolling_metrics(self.df)
        
        print("\n" + "=" * 60)
        print("✓ PROCESAMIENTO COMPLETADO")
        print("=" * 60)
        print(f"\nDataFrame final: {len(self.df)} partidos")
        print(f"Columnas: {len(self.df.columns)}")
        print(f"\nColumnas de métricas creadas:")
        metric_cols = [col for col in self.df.columns if 'Rolling' in col]
        for col in metric_cols:
            print(f"  - {col}")
        
        return self.df


def main():
    """Función principal para ejecutar el procesador."""
    processor = FootballDataProcessor(data_dir="DATOS")
    df = processor.process_all()
    
    # Mostrar muestra de datos
    print("\n" + "=" * 60)
    print("MUESTRA DE DATOS PROCESADOS")
    print("=" * 60)
    print(df[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 
              'Home_Rolling_Goals', 'Away_Rolling_Goals']].head(10))
    
    return df


if __name__ == "__main__":
    df = main()

