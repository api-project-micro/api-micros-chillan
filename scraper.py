import json
from playwright.sync_api import sync_playwright

# Búsquedas directas de paradas de autobús enfocadas en Chillán
ENLACES_SECTORES = {
    "Centro": "https://www.google.com/maps/search/parada%20de%20autobus%20Centro%20Chillan",
    "Doña Francisca": "https://www.google.com/maps/search/parada%20de%20autobus%20Do%C3%B1a%20Francisca%20Chillan",
    "Las Termas": "https://www.google.com/maps/search/parada%20de%20autobus%20Las%20Termas%20Chillan",
    "Sol de Oriente": "https://www.google.com/maps/search/parada%20de%20autobus%20Sol%20de%20Oriente%20Chillan",
    "Ultraestación": "https://www.google.com/maps/search/parada%20de%20autobus%20Ultraestacion%20Chillan",
    "Vicente Méndez": "https://www.google.com/maps/search/parada%20de%20autobus%20Vicente%20Mendez%20Chillan",
    "Río Viejo": "https://www.google.com/maps/search/parada%20de%20autobus%20Rio%20Viejo%20Chillan",
    "Los Volcanes": "https://www.google.com/maps/search/parada%20de%20autobus%20Los%20Volcanes%20Chillan",
    "Santa Elvira": "https://www.google.com/maps/search/parada%20de%20autobus%20Santa%20Elvira%20Chillan",
    "Parque Los Alerces": "https://www.google.com/maps/search/parada%20de%20autobus%20Parque%20Los%20Alerces%20Chillan"
}

def ejecutar_scraper():
    resultados = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for sector, url in ENLACES_SECTORES.items():
            print(f"Procesando sector: {sector}")
            try:
                page.goto(url, timeout=60000)
                page.wait_for_timeout(4000)
                
                # Nombre seguro para capturas de depuración
                slug_sector = sector.lower().replace(' ', '_').replace('ñ', 'n').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                page.screenshot(path=f"debug_{slug_sector}.jpg")

                resultados[sector] = {
                    "estado": "OK",
                    "url": url
                }

            except Exception as e:
                print(f"Error procesando {sector}: {e}")
                resultados[sector] = {
                    "estado": "Error",
                    "detalles": str(e)
                }

        browser.close()

    with open("horarios_micros.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    ejecutar_scraper()
