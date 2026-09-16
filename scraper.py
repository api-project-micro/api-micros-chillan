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
        
        url = "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.6004151,-72.0997396,18z?entry=ttu&g_ep=EgoyMDI2MDkxMy4wIKXMDSoASAFQAw%3D%3D"
        print("Conectando a Google Maps...")
        
        paraderos_totales = []
        patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            
            try:
                page.wait_for_selector("a.hfpxzc", state="visible", timeout=25000)
            except TimeoutError:
                print("No se pudieron cargar los resultados iniciales de paraderos.")
                return
            
            resultados_paradas = page.locator("a.hfpxzc").all()
            print(f"=== PARADAS DETECTADAS: {len(resultados_paradas)} ===")
            
            max_paraderos = min(len(resultados_paradas), 5)
            
            for i in range(max_paraderos):
                try:
                    print(f"\n--- Procesando paradero {i + 1} de {max_paraderos} ---")
                    
                    resultados = page.locator("a.hfpxzc").all()
                    if i >= len(resultados):
                        break
                        
                    paradero_link = resultados[i]
                    nombre_paradero = paradero_link.get_attribute("aria-label") or f"Paradero {i + 1}"
                    print(f"Nombre obtenido: {nombre_paradero}")
                    
                    paradero_link.scroll_into_view_if_needed()
                    paradero_link.click()
                    page.wait_for_timeout(3000)
                    
                    horarios_paradero = []
                    
                    # 1. Intentar hacer clic en el botón 'Ver el panel de salidas'
                    btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas'), [aria-label*='panel de salidas']").first
                    if btn_salidas.is_visible(timeout=3000):
                        try:
                            btn_salidas.click()
                            page.wait_for_timeout(3000)
                        except Exception:
                            pass
                    
                    # 2. Hacer scroll en la ficha lateral
                    panel_lateral = page.locator("div[role='main']").first
                    if panel_lateral.is_visible():
                        for _ in range(2):
                            panel_lateral.mouse_wheel(0, 300)
                            page.wait_for_timeout(500)
                    
                    # 3. Intentar extraer horarios del panel de salidas si está disponible
                    filas = page.locator("div.iP2t7d, div.n5vinf, div.Fkgn4d, div.M75A3b, div[role='listitem']").all()
                    for fila in filas:
                        try:
                            texto_fila = fila.inner_text().strip()
                            if not texto_fila:
                                continue
                            
                            lineas = [l.strip() for l in texto_fila.split("\n") if l.strip()]
                            hora_encontrada = None
                            
                            for l in lineas:
                                match = patron_hora.search(l)
                                if match:
                                    hora_encontrada = match.group(0)
                                    break
                            
                            if hora_encontrada:
                                textos_limpios = [l for l in lineas if l != hora_encontrada]
                                detalle_final = " - ".join(textos_limpios) if textos_limpios else "Recorrido urbano"
                                item = {"detalle": detalle_final, "hora": hora_encontrada}
                                if item not in horarios_paradero:
                                    horarios_paradero.append(item)
                        except Exception:
                            continue
                    
                    # 4. Fallback: Si no hay horarios dinámicos, extraer los distintivos/números de micro (ej: badge '10' bajo Autobuses)
                    if not horarios_paradero and panel_lateral.is_visible():
                        texto_panel = panel_lateral.inner_text()
                        
                        # Buscar los botones/badges con los números de las micros
                        badges = page.locator("div:has-text('Autobuses') ~ div button, div:has-text('Autobuses') ~ div span").all()
                        lineas_detectadas = []
                        for b in badges:
                            txt = b.inner_text().strip()
                            if txt.isdigit() and len(txt) <= 4 and txt not in lineas_detectadas:
                                lineas_detectadas.append(txt)
                        
                        if lineas_detectadas:
                            for linea_num in lineas_detectadas:
                                horarios_paradero.append({
                                    "detalle": f"Línea {linea_num}",
                                    "hora": "Frecuencia regular"
                                })
                        elif "Autobuses" in texto_panel:
                            lineas_texto = [l.strip() for l in texto_panel.split("\n") if l.strip()]
                            for idx, l in enumerate(lineas_texto):
                                if l == "Autobuses" and idx + 1 < len(lineas_texto):
                                    lineas_detectadas.append(lineas_texto[idx + 1])
                                    horarios_paradero.append({
                                        "detalle": f"Línea {lineas_texto[idx + 1]}",
                                        "hora": "Frecuencia regular"
                                    })

                    print(f"Rutas/Horarios capturados para {nombre_paradero}: {len(horarios_paradero)}")
                    
                    paraderos_totales.append({
                        "id": f"paradero_{i + 1}",
                        "nombre": nombre_paradero,
                        "rutas": horarios_paradero
                    })
                    
                    # Volver a la lista principal
                    btn_atras = page.locator("button[aria-label*='Atrás'], button[aria-label*='Volver']").first
                    if btn_atras.is_visible(timeout=2000):
                        btn_atras.click()
                    else:
                        page.go_back()
                    
                    page.wait_for_timeout(2000)
                    
                except Exception as inner_ex:
                    print(f"Error procesando paradero: {inner_ex}")
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    continue

        except Exception as e:
            print(f"Error general durante la ejecución: {e}")
            
        finally:
            browser.close()
        
        if not paraderos_totales:
            print("⚠️ No se pudieron extraer paraderos.")
            return
            
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M hrs")
        resultado_final = {
            "ciudad": "Chillán",
            "actualizado_en": fecha_actual,
            "paraderos": paraderos_totales
        }
        
        with open("horarios_micros.json", "w", encoding="utf-8") as f:
            json.dump(resultado_final, f, ensure_ascii=False, indent=4)
            
        print(f"\n¡Éxito total! Se actualizaron {len(paraderos_totales)} paraderos en horarios_micros.json.")

if __name__ == "__main__":
    extraer_todos_los_paraderos()
