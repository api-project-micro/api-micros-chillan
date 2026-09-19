import json
import time
from datetime import datetime
from urllib.parse import quote
from playwright.sync_api import sync_playwright

CUADRANTES = [
    "Centro",
    "Doña Francisca",
    "Las Termas",
    "Sol de Oriente",
    "Ultraestacion",
    "Vicente Mendez",
    "Rio Viejo",
    "Los Volcanes",
    "Santa Elvira",
    "Parque Los Alerces"
]

def manejar_cookies(page):
    try:
        if "consent.google" in page.url:
            print("    [!] Pantalla de cookies detectada. Intentando aceptar...")
            page.locator("button:has-text('Aceptar todo'), button:has-text('Accept all')").first.click(timeout=5000)
            page.wait_for_load_state("networkidle")
        else:
            page.locator("button:has-text('Aceptar todo'), button:has-text('Accept all')").click(timeout=3000)
    except Exception:
        pass

def hacer_scroll_completo(page):
    try:
        panel_results = page.locator('div[role="feed"]')
        if panel_results.count() == 0:
            return

        last_height = 0
        for _ in range(3):
            panel_results.evaluate("el => el.scrollTop = el.scrollHeight")
            time.sleep(2.0)
            new_height = panel_results.evaluate("el => el.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    except Exception:
        pass

def ejecutar_scraper():
    paraderos_map = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="es-CL",
            geolocation={"longitude": -72.1013534, "latitude": -36.6104272}, # Coordenadas de Chillán
            permissions=["geolocation"]
        )
        page = context.new_page()

        print("=== Iniciando Scraper de Paraderos por Cuadrantes (Chillán) ===")

        for sector in CUADRANTES:
            query = f"parada de autobus {sector} Chillan"
            url_busqueda = f"https://www.google.com/maps/search/{quote(query)}"
            print(f"\n[+] Buscando en cuadrante: {sector}...")

            try:
                page.goto(url_busqueda, wait_until="networkidle", timeout=35000)
                manejar_cookies(page)
                
                print(f"    - URL actual: {page.url}")
                print(f"    - Título de la página: {page.title()}")

                try:
                    page.wait_for_selector('div[role="feed"], a[href*="/maps/place/"]', timeout=8000)
                except Exception:
                    print("    [!] El feed de resultados no cargó a tiempo.")

                hacer_scroll_completo(page)

                enlaces_paraderos = page.locator('a.hfpxzc, a[href*="/maps/place/"]').all()
                print(f"    - Encontrados en {sector}: {len(enlaces_paraderos)} tarjetas.")

                # Si encuentra 0 resultados, guarda una captura para análisis
                if len(enlaces_paraderos) == 0:
                    foto_path = f"debug_{sector.replace(' ', '_')}.png"
                    page.screenshot(path=foto_path)
                    print(f"    [!] Captura guardada como {foto_path} para inspeccionar.")

                for enlace in enlaces_paraderos:
                    try:
                        url = enlace.get_attribute("href")
                        nombre = enlace.get_attribute("aria-label") or enlace.inner_text()
                        if not url or not nombre or len(nombre.strip()) < 3:
                            continue
                        
                        url_limpia = url.split("?")[0]
                        if url_limpia not in paraderos_map:
                            paraderos_map[url_limpia] = {
                                "nombre": nombre.strip().split("\n")[0],
                                "url": url,
                                "salidas": [] 
                            }
                    except Exception:
                        continue

            except Exception as e:
                print(f"    [!] Error al procesar sector {sector}: {e}")

        browser.close()

    lista_paraderos = []
    for index, (url_key, datos) in enumerate(paraderos_map.items(), start=1):
        datos["id"] = f"paradero_{index}"
        lista_paraderos.append(datos)

    resultado_final = {
        "ciudad": "Chillán",
        "actualizado_en": datetime.now().strftime("%Y-%m-%d %H:%M hrs"),
        "paraderos_totales_registrados": len(lista_paraderos),
        "paraderos": lista_paraderos
    }

    with open("horarios_micros.json", "w", encoding="utf-8") as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=4)

    print(f"\n[✔] Proceso finalizado exitosamente.")
    print(f"[✔] Total de paraderos únicos registrados: {len(lista_paraderos)}")

if __name__ == "__main__":
    ejecutar_scraper()
