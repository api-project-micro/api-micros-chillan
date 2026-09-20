import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

# 10 Cuadrantes / Sectores en Chillán
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
            viewport={"width": 1280, "height": 720},
            extra_http_headers={"Accept-Language": "es-CL,es;q=0.9"}
        )
        
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        
        patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
        patron_linea = re.compile(r'^\d+[A-Za-z]?$')  # Acepta números (4) o alfanuméricos (2A)
        
        paraderos_totales = []
        nombres_procesados = set()

        for sector, url in ENLACES_SECTORES.items():
            print(f"\n==========================================")
            print(f" Escaneando sector: {sector}")
            print(f"==========================================")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                
                # Aceptar cookies si aparece el botón
                try:
                    btn_cookie = page.locator("button:has-text('Aceptar todo'), button:has-text('Accept all')").first
                    if btn_cookie.is_visible(timeout=2000):
                        btn_cookie.click()
                        page.wait_for_timeout(1000)
                except Exception:
                    pass
                
                # Esperar a que aparezcan los resultados
                try:
                    page.wait_for_selector("a.hfpxzc", state="visible", timeout=15000)
                except TimeoutError:
                    print(f"No se encontraron paraderos en el sector {sector}.")
                    continue
                
                # Hacer scroll en el panel izquierdo para cargar la lista completa
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
                        
                        # Omitir si ya fue procesado en otro sector
                        if nombre_paradero in nombres_procesados:
                            continue
                        
                        nombres_procesados.add(nombre_paradero)
                        print(f"  [{len(paraderos_totales) + 1}] Entrando a: {nombre_paradero}")
                        
                        # Abrir la ficha del paradero
                        paradero_link.scroll_into_view_if_needed()
                        paradero_link.click()
                        page.wait_for_timeout(2000)
                        
                        salidas_programadas = []
                        btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
                        
                        # Abrir el panel de salidas si está disponible
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
                                
                            print(f"     -> Se capturaron {len(salidas_programadas)} salidas programadas.")
                            
                            # Volver al detalle del paradero
                            btn_atras = page.locator("button[aria-label*='Atrás'], button[aria-label*='Volver']").first
                            if btn_atras.is_visible(timeout=2000):
                                btn_atras.click()
                                page.wait_for_timeout(1000)
                        else:
                            print("     -> Este paradero no dispone de 'Panel de salidas'.")
                            
                        paraderos_totales.append({
                            "id": f"paradero_{len(paraderos_totales) + 1}",
                            "sector": sector,
                            "nombre": nombre_paradero,
                            "salidas": salidas_programadas
                        })
                        
                        # Volver a la lista del sector
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

        # Guardar resultados
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
