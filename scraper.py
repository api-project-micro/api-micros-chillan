import json
import time
import re
from datetime import datetime
from urllib.parse import quote
from playwright.sync_api import sync_playwright, TimeoutError

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

def normalizar_hora(hora_str):
    """Convierte horas como '7:49 a.m.' o '14:30' a formato 24h 'HH:mm' para Kotlin"""
    try:
        limpio = hora_str.lower().replace(".", "").strip()
        if "am" in limpio or "pm" in limpio:
            limpio = limpio.replace("a m", "am").replace("p m", "pm")
            dt = datetime.strptime(limpio, "%I:%M %p") if " " in limpio else datetime.strptime(limpio, "%I:%M%p")
            return dt.strftime("%H:%M")
        elif ":" in limpio:
            dt = datetime.strptime(limpio, "%H:%M")
            return dt.strftime("%H:%M")
    except Exception:
        pass
    return hora_str

def manejar_cookies(page):
    try:
        if "consent.google" in page.url:
            print("    [!] Pantalla cookies detectada. Aceptando...")
            page.locator("button:has-text('Aceptar todo'), button:has-text('Accept all')").first.click(timeout=5000)
            page.wait_for_timeout(2000)
    except Exception:
        pass

def hacer_scroll_completo(page):
    print("    Cargando lista completa de paraderos del cuadrante...")
    prev_count = 0
    for _ in range(15):
        page.evaluate("""
            const feed = document.querySelector('div[role="feed"]');
            if (feed) { feed.scrollBy(0, 1500); }
        """)
        page.wait_for_timeout(1000)
        current_count = len(page.locator("a.hfpxzc").all())
        if current_count == prev_count and current_count > 0:
            break
        prev_count = current_count

def ejecutar_scraper():
    paraderos_map = {} # Diccionario global para deduplicar paraderos entre cuadrantes
    patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled", # Del scraper viejo
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1280,800",
                "--lang=es-CL"
            ]
        )
        
        # Configuración anti-bot y de geolocalización (Híbrido)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            locale="es-CL",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"Accept-Language": "es-CL,es;q=0.9"},
            geolocation={"longitude": -72.1013534, "latitude": -36.6104272},
            permissions=["geolocation"]
        )
        # Script clave del Scraper Viejo para evadir bloqueos
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        print("=== Iniciando Scraper de Paraderos por Cuadrantes (Chillán) ===")

        for sector in CUADRANTES:
            query = f"parada de autobus {sector} Chillan"
            url_busqueda = f"https://www.google.com/maps/search/{quote(query)}"
            print(f"\n[+] Buscando en cuadrante: {sector}...")

            try:
                # Usamos domcontentloaded del viejo en vez de networkidle del nuevo
                page.goto(url_busqueda, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                manejar_cookies(page)

                try:
                    page.wait_for_selector('a.hfpxzc', state="visible", timeout=25000)
                except TimeoutError:
                    print(f"    [!] No se encontraron paraderos a tiempo en {sector}.")
                    foto_path = f"debug_{sector.replace(' ', '_')}.png"
                    page.screenshot(path=foto_path)
                    print(f"    [!] Captura guardada como {foto_path}")
                    continue

                hacer_scroll_completo(page)

                paradas = page.locator('a.hfpxzc').all()
                print(f"    - Encontrados en {sector}: {len(paradas)} tarjetas.")

                if len(paradas) == 0:
                    foto_path = f"debug_{sector.replace(' ', '_')}.png"
                    page.screenshot(path=foto_path)
                    continue

                # Bucle de extracción del Scraper Viejo adaptado
                for i in range(len(paradas)):
                    try:
                        # Re-localizamos para evitar errores de elementos caducados en el DOM
                        paradas_actuales = page.locator('a.hfpxzc').all()
                        if i >= len(paradas_actuales):
                            break
                        
                        paradero_link = paradas_actuales[i]
                        url_paradero = paradero_link.get_attribute("href")
                        
                        url_limpia = url_paradero.split("?")[0] if url_paradero else f"{sector}_{i}"
                        
                        # DEDUPLICACIÓN: Si la URL ya está en el mapa, la saltamos (cruces de cuadrantes)
                        if url_limpia in paraderos_map:
                            continue

                        nombre_paradero = paradero_link.get_attribute("aria-label") or f"Paradero {i + 1}"
                        print(f"    [{i + 1}/{len(paradas_actuales)}] Entrando a: {nombre_paradero}")

                        paradero_link.scroll_into_view_if_needed()
                        paradero_link.click()
                        page.wait_for_timeout(2000)

                        salidas_programadas = []
                        btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
                        
                        if btn_salidas.is_visible(timeout=3000):
                            print("      -> Extrayendo horarios...")
                            btn_salidas.click()
                            page.wait_for_timeout(2500)
                            
                            panel_activo = page.locator("div[role='main']").last
                            texto_panel = panel_activo.inner_text()
                            
                            lineas_texto = [line.strip() for line in texto_panel.split('\n') if line.strip()]
                            idx = 0
                            while idx < len(lineas_texto):
                                item = lineas_texto[idx]
                                if item.isdigit() and len(item) <= 3:
                                    linea_num = item
                                    destino = lineas_texto[idx + 1] if (idx + 1 < len(lineas_texto)) else "Sin destino"
                                    
                                    hora_encontrada = None
                                    for offset in range(2, 5):
                                        if idx + offset < len(lineas_texto):
                                            posible_hora = lineas_texto[idx + offset]
                                            if patron_hora.search(posible_hora):
                                                hora_encontrada = posible_hora
                                                break
                                                
                                    if hora_encontrada:
                                        salidas_programadas.append({
                                            "linea": f"Línea {linea_num}",
                                            "destino": destino,
                                            "hora": normalizar_hora(hora_encontrada) # Aplicamos la normalización
                                        })
                                idx += 1
                            print(f"         ¡Capturadas {len(salidas_programadas)} salidas!")
                            
                            btn_atras = page.locator("button[aria-label*='Atrás'], button[aria-label*='Volver']").first
                            if btn_atras.is_visible(timeout=2000):
                                btn_atras.click()
                                page.wait_for_timeout(1000)
                        else:
                            print("      -> Sin panel de salidas.")

                        # Guardamos en el diccionario global (fusionando resultados de todos los cuadrantes)
                        paraderos_map[url_limpia] = {
                            "nombre": nombre_paradero,
                            "url": url_paradero,
                            "salidas": salidas_programadas
                        }

                        # Volver a la lista del cuadrante actual
                        btn_atras_principal = page.locator("button[aria-label*='Atrás'], button[aria-label*='Volver']").first
                        if btn_atras_principal.is_visible(timeout=2000):
                            btn_atras_principal.click()
                            page.wait_for_timeout(1000)
                            
                    except Exception as inner_ex:
                        print(f"      [!] Error en paradero {i + 1}: {inner_ex}")
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(1500)
                        continue

            except Exception as e:
                print(f"    [!] Error al procesar sector {sector}: {e}")

        browser.close()

    # Convertir el mapa de deduplicación de nuevo a una lista para el JSON
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
