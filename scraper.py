import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

# Enlaces explícitos formateados con búsqueda focalizada en Chillán y coordenadas GPS
ENLACES_SECTORES = {
    "Centro": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Centro,+Chill%C3%A1n,+Chile/@-36.6063,-72.1023,15z/data=!3m1!4b1?entry=ttu",
    "Doña Francisca": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Dona+Francisca,+Chill%C3%A1n,+Chile/@-36.6212,-72.0725,15z/data=!3m1!4b1?entry=ttu",
    "Las Termas": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Las+Termas,+Chill%C3%A1n,+Chile/@-36.6201,-72.0834,15z/data=!3m1!4b1?entry=ttu",
    "Sol de Oriente": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Sol+de+Oriente,+Chill%C3%A1n,+Chile/@-36.6134,-72.0712,15z/data=!3m1!4b1?entry=ttu",
    "Ultraestación": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Ultraestacion,+Chill%C3%A1n,+Chile/@-36.6045,-72.1156,15z/data=!3m1!4b1?entry=ttu",
    "Vicente Méndez": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Vicente+Mendez,+Chill%C3%A1n,+Chile/@-36.5898,-72.0881,15z/data=!3m1!4b1?entry=ttu",
    "Río Viejo": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+rio+viejo,+Chill%C3%A1n,+Chile/@-36.6369505,-72.0823686,15z/data=!3m1!4b1?entry=ttu",
    "Los Volcanes": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Los+Volcanes,+Chill%C3%A1n,+Chile/@-36.6189,-72.0623,15z/data=!3m1!4b1?entry=ttu",
    "Santa Elvira": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Santa+Elvira,+Chill%C3%A1n,+Chile/@-36.5921,-72.1089,15z/data=!3m1!4b1?entry=ttu",
    "Parque Los Alerces": "https://www.google.com/maps/search/parada+de+autobus+cerca+de+Parque+Los+Alerces,+Chill%C3%A1n,+Chile/@-36.6312,-72.0890,15z/data=!3m1!4b1?entry=ttu"
}

def ejecutar_scraper():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1280,720",
                "--lang=es-CL"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            locale="es-CL",
            geolocation={"latitude": -36.6063, "longitude": -72.1023},
            permissions=["geolocation"],
            viewport={"width": 1280, "height": 720},
            extra_http_headers={"Accept-Language": "es-CL,es;q=0.9"}
        )
        
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        
        patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
        patron_linea = re.compile(r'^\d+[A-Za-z]?$')
        
        paraderos_totales = []
        nombres_procesados = set()

        for sector, url in ENLACES_SECTORES.items():
            print(f"\n==========================================")
            print(f" Escaneando sector: {sector}")
            print(f"==========================================")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000)
                
                # Aceptar aviso de cookies si aparece
                try:
                    btn_cookie = page.locator("button:has-text('Aceptar todo'), button:has-text('Accept all'), form[action*='consent'] button").first
                    if btn_cookie.is_visible(timeout=3000):
                        btn_cookie.click()
                        page.wait_for_timeout(1500)
                except Exception:
                    pass
                
                # Esperar a que cargue la lista de paraderos
                try:
                    page.wait_for_selector("a.hfpxzc", state="visible", timeout=20000)
                except TimeoutError:
                    print(f"No se encontraron paraderos en {sector}.")
                    slug = sector.lower().replace(' ', '_').replace('ñ', 'n')
                    page.screenshot(path=f"debug_{slug}.png")
                    continue
                
                # Scroll para cargar la lista completa
                prev_count = 0
                for _ in range(8):
                    page.evaluate("""
                        const feed = document.querySelector('div[role="feed"]');
                        if (feed) { feed.scrollBy(0, 1500); }
                    """)
                    page.wait_for_timeout(1000)
                    current_count = len(page.locator("a.hfpxzc").all())
                    if current_count == prev_count:
                        break
                    prev_count = current_count
                
                paradas = page.locator("a.hfpxzc").all()
                print(f"Encontrados {len(paradas)} paraderos en la lista de {sector}.")
                
                for i in range(len(paradas)):
                    try:
                        paradas = page.locator("a.hfpxzc").all()
                        if i >= len(paradas):
                            break
                            
                        paradero_link = paradas[i]
                        nombre_paradero = paradero_link.get_attribute("aria-label") or f"Paradero {len(paraderos_totales) + 1}"
                        
                        if nombre_paradero in nombres_procesados:
                            continue
                        
                        nombres_procesados.add(nombre_paradero)
                        print(f"  [{len(paraderos_totales) + 1}] Entrando a: {nombre_paradero}")
                        
                        paradero_link.scroll_into_view_if_needed()
                        paradero_link.click()
                        page.wait_for_timeout(2000)
                        
                        salidas_programadas = []
                        btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
                        
                        if btn_salidas.is_visible(timeout=3000):
                            btn_salidas.click()
                            page.wait_for_timeout(2000)
                            
                            panel_activo = page.locator("div[role='main']").last
                            texto_panel = panel_activo.inner_text()
                            lineas_texto = [line.strip() for line in texto_panel.split('\n') if line.strip()]
                            
                            idx = 0
                            while idx < len(lineas_texto):
                                item = lineas_texto[idx]
                                if patron_linea.match(item) and len(item) <= 4:
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
                                            "hora": hora_encontrada
                                        })
                                idx += 1
                                
                            print(f"     -> Capturadas {len(salidas_programadas)} salidas.")
                            
                            btn_atras = page.locator("button[aria-label*='Atrás'], button[aria-label*='Volver']").first
                            if btn_atras.is_visible(timeout=2000):
                                btn_atras.click()
                                page.wait_for_timeout(1000)
                        else:
                            print("     -> Sin panel de salidas.")
                            
                        paraderos_totales.append({
                            "id": f"paradero_{len(paraderos_totales) + 1}",
                            "sector": sector,
                            "nombre": nombre_paradero,
                            "salidas": salidas_programadas
                        })
                        
                        btn_atras_principal = page.locator("button[aria-label*='Atrás'], button[aria-label*='Volver']").first
                        if btn_atras_principal.is_visible(timeout=2000):
                            btn_atras_principal.click()
                            page.wait_for_timeout(1000)
                            
                    except Exception as inner_ex:
                        print(f"     -> Error procesando paradero: {inner_ex}")
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(1500)
                        continue

            except Exception as sector_ex:
                print(f"Error procesando el sector {sector}: {sector_ex}")

        browser.close()

        resultado_final = {
            "ciudad": "Chillán",
            "actualizado_en": datetime.now().strftime("%Y-%m-%d %H:%M hrs"),
            "total_paraderos": len(paraderos_totales),
            "paraderos": paraderos_totales
        }
        
        with open("horarios_micros.json", "w", encoding="utf-8") as f:
            json.dump(resultado_final, f, ensure_ascii=False, indent=4)
            
        print(f"\n¡Extracción finalizada! Se guardaron {len(paraderos_totales)} paraderos únicos en 'horarios_micros.json'.")

if __name__ == "__main__":
    ejecutar_scraper()
