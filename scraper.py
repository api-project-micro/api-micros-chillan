import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

def extraer_todos_los_paraderos():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
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
        
        url = "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.6004151,-72.0997396,18z?entry=ttu"
        print("Conectando a Google Maps...")
        
        paraderos_totales = []
        patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
        # Regex para aceptar números solos o con letras (ej. 10, 13BV, 4V1)
        patron_linea = re.compile(r'^\d+[A-Za-z0-9]*$')
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            
            try:
                page.wait_for_selector("a.hfpxzc", state="visible", timeout=25000)
            except TimeoutError:
                print("No se encontraron paraderos en la zona.")
                return
            
            # 1. Cargar la lista completa de paraderos con scroll (Nivel 1)
            print("Cargando lista completa de paraderos...")
            prev_count = 0
            for _ in range(15):
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
            print(f"=== TOTAL DE PARADAS A PROCESAR: {len(paradas)} ===")
            
            for i in range(len(paradas)):
                try:
                    paradas = page.locator("a.hfpxzc").all()
                    if i >= len(paradas):
                        break
                        
                    paradero_link = paradas[i]
                    nombre_paradero = paradero_link.get_attribute("aria-label") or f"Paradero {i + 1}"
                    print(f"\n[{i + 1}/{len(paradas)}] Entrando a: {nombre_paradero}")
                    
                    # Clic para abrir ficha de paradero (Nivel 2)
                    paradero_link.scroll_into_view_if_needed()
                    paradero_link.click()
                    page.wait_for_timeout(2000)
                    
                    salidas_programadas = []
                    
                    # Localizar y presionar 'Ver el panel de salidas' (Nivel 2 -> Nivel 3)
                    btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
                    
                    if btn_salidas.is_visible(timeout=3000):
                        print("  -> Abriendo el 'Panel de salidas'...")
                        btn_salidas.click()
                        page.wait_for_timeout(2500)
                        
                        panel_activo = page.locator("div[role='main']").last
                        texto_panel = panel_activo.inner_text()
                        
                        lineas_texto = [line.strip() for line in texto_panel.split('\n') if line.strip()]
                        
                        idx = 0
                        while idx < len(lineas_texto):
                            item = lineas_texto[idx]
                            
                            # Validación actualizada: acepta números y variantes con letras
                            if patron_linea.match(item) and len(item) <= 6:
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
                        
                        print(f"     ¡Capturadas {len(salidas_programadas)} salidas programadas!")
                        
                        # Volver del Nivel 3 al Nivel 2
                        btn_atras = page.locator("button[aria-label*='Atrás'], button[aria-label*='Volver']").first
                        if btn_atras.is_visible(timeout=2000):
                            btn_atras.click()
                            page.wait_for_timeout(1000)
                    else:
                        print("  -> Este paradero no dispone de 'Panel de salidas'.")
                        
                    paraderos_totales.append({
                        "id": f"paradero_{i + 1}",
                        "nombre": nombre_paradero,
                        "salidas": salidas_programadas
                    })
                    
                    # Volver al Nivel 1 (Lista)
                    btn_atras_principal = page.locator("button[aria-label*='Atrás'], button[aria-label*='Volver']").first
                    if btn_atras_principal.is_visible(timeout=2000):
                        btn_atras_principal.click()
                        page.wait_for_timeout(1000)
                        
                except Exception as inner_ex:
                    print(f"Error en paradero {i + 1}: {inner_ex}")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1500)
                    continue

        except Exception as e:
            print(f"Error general durante la ejecución: {e}")
        finally:
            browser.close()
            
        resultado_final = {
            "ciudad": "Chillán",
            "actualizado_en": datetime.now().strftime("%Y-%m-%d %H:%M hrs"),
            "paraderos": paraderos_totales
        }
        
        with open("horarios_micros.json", "w", encoding="utf-8") as f:
            json.dump(resultado_final, f, ensure_ascii=False, indent=4)
            
        print(f"\n¡Éxito! Se guardaron {len(paraderos_totales)} paraderos con sus horarios en horarios_micros.json.")

if __name__ == "__main__":
    extraer_todos_los_paraderos()
