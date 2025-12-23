"""
Motor de Noticias - Anti-Bloqueo
"""
import time
import random

def get_live_context(local, visitante):
    """
    Busca contexto en internet. 
    Devuelve siempre un dict: {'texto': str, 'status': str, 'fuentes': list}
    """
    
    # Imports seguros dentro de la función para no romper app si faltan libs
    try:
        from duckduckgo_search import DDGS
        import trafilatura
    except ImportError:
        return {"texto": "NO_HAY_NOTICIAS (Faltan librerías)", "status": "missing"}

    local = str(local).strip()
    visitante = str(visitante).strip()
    
    # Query única combinada
    query = f"Previa alineaciones bajas {local} vs {visitante} marca as futbolfantasy"
    
    print(f"📡 Buscando noticias: {local} vs {visitante}...")
    
    resumen_parts = []
    fuentes = []
    
    try:
        with DDGS() as ddgs:
            # Buscamos 2 resultados máximo
            results = list(ddgs.text(query, max_results=2))
            
            for r in results:
                title = r.get('title', 'Noticia')
                url = r.get('href', '')
                
                if url:
                    try:
                        downloaded = trafilatura.fetch_url(url)
                        if downloaded:
                            text = trafilatura.extract(downloaded)
                            if text:
                                # Limpiamos texto y cogemos un fragmento relevante
                                snippet = " ".join(text.split())[:600]
                                resumen_parts.append(f"--- {title} ---\n{snippet}...")
                                fuentes.append(title)
                        time.sleep(random.uniform(0.5, 1.0)) # Pausa humana
                    except:
                        continue

    except Exception as e:
        print(f"Error conexión noticias: {e}")
        return {"texto": "NO_HAY_NOTICIAS (Error conexión)", "status": "missing"}

    if not resumen_parts:
        return {"texto": "NO_HAY_NOTICIAS", "status": "missing"}
    
    return {
        "texto": "\n\n".join(resumen_parts),
        "status": "ok",
        "fuentes": fuentes
    }