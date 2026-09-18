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
                "--window-size=1280,720",
                "--lang=es-CL"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            locale="es-CL",
            viewport={"width": 1280, "height": 720}
        )
        
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        
        # Tip: Si buscas por cuadrículas/sectores (ej. "Parada de autobús Oriente Chillán"), superarás el límite de ~120 de Google.
        url = "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.6151805,-72.1325271,13z?entry=ttu"
        print("Conectando a Google Maps...")
        
        paraderos_totales = []
        patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
        patron_linea = re.compile(r'^\d+[A-Za-z0-9]*$')
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            
            try:
                page.wait_for_selector("a.hfpxzc", state="visible", timeout=25000)
            except TimeoutError:
                print("No se encontraron paraderos.")
                return

            # =========================================================
            # FASE 1: Scroll continuo e infinito para capturar URLs
            # =========================================================
            print("Cargando lista completa con scroll dinámico...")
            
            intentos_sin_cambio = 0
            urls_paraderos = []
            
            while intentos_sin_cambio < 5:
                page.evaluate("""
                    const feed = document.querySelector('div[role="feed"]');
                    if (feed) { feed.scrollBy(0, 3000); }
                """)
                page.wait_for_timeout(1500)
                
                elementos = page.locator("a.hfpxzc").all()
                nuevas_urls = [el.get_attribute("href") for el in elementos if el.get_attribute("href")]
                
                # Eliminar duplicados manteniendo orden
                for u in nuevas_urls:
                    if u not in urls_paraderos:
                        urls_paraderos.append(u)
                
                print(f"Paraderos detectados hasta ahora: {len(urls_paraderos)}")
                
                # Comprobar si llegó al final explícito de Google Maps
                texto_final = page.locator("text='Has llegado al final de la lista'").is_visible()
                if texto_final:
                    print("Se alcanzó el final de la lista de Google Maps.")
                    break
                    
                if len(nuevas_urls) == len(urls_paraderos):
                    intentos_sin_cambio += 1
                else:
                    intentos_sin_cambio = 0

            print(f"\n=== TOTAL DE URLS ÚNICAS ENCONTRADAS: {len(urls_paraderos)} ===")

            # =========================================================
            # FASE 2: Procesar cada paradero mediante navegación directa
            # =========================================================
            for i, url_paradero in enumerate(urls_paraderos):
                try:
                    print(f"\n[{i + 1}/{len(urls_paraderos)}] Navegando a paradero...")
                    page.goto(url_paradero, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                    
                    # Nombre del paradero
                    h1 = page.locator("h1").first
                    nombre_paradero = h1.inner_text() if h1.is_visible() else f"Paradero {i + 1}"
                    
                    salidas_programadas = []
                    
                    # Buscar el botón 'Ver el panel de salidas'
                    btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
                    
                    if btn_salidas.is_visible(timeout=3000):
                        print(f"  -> Extrayendo panel de salidas de: {nombre_paradero}")
                        btn_salidas.click()
                        page.wait_for_timeout(2000)
                        
                        panel_activo = page.locator("div[role='main']").last
                        texto_panel = panel_activo.inner_text()
                        lineas_texto = [line.strip() for line in texto_panel.split('\n') if line.strip()]
                        
                        idx = 0
                        while idx < len(lineas_texto):
                            item = lineas_texto[idx]
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
                        print(f"     ¡{len(salidas_programadas)} salidas capturadas!")
                    
                    paraderos_totales.append({
                        "id": f"paradero_{i + 1}",
                        "nombre": nombre_paradero,
                        "salidas": salidas_programadas
                    })

                except Exception as inner_ex:
                    print(f"Error procesando paradero {i + 1}: {inner_ex}")
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
            
        print(f"\n¡Proceso finalizado! Se guardaron {len(paraderos_totales)} paraderos.")

if __name__ == "__main__":
    extraer_todos_los_paraderos()
