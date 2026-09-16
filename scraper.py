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
        
        # Ocultar propiedad navigator.webdriver
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = context.new_page()
        
        # URL exacta proporcionada
        url = "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.6004151,-72.0997396,18z?entry=ttu&g_ep=EgoyMDI2MDkxMy4wIKXMDSoASAFQAw%3D%3D"
        print("Conectando a Google Maps con el enlace directo de paraderos...")
        
        paraderos_totales = []
        patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
        
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            
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
                    
                    btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
                    horarios_paradero = []
                    
                    try:
                        btn_salidas.wait_for(state="visible", timeout=10000)
                        btn_salidas.click()
                        
                        page.wait_for_selector("div.iP2t7d, div.n5vinf, div.Fkgn4d", timeout=12000)
                        
                        print("Haciendo scroll en el panel para cargar más rutas...")
                        for _ in range(4):
                            filas_actuales = page.locator("div.iP2t7d, div.n5vinf, div.Fkgn4d").all()
                            if filas_actuales:
                                try:
                                    filas_actuales[-1].scroll_into_view_if_needed()
                                    page.wait_for_timeout(1000)
                                except:
                                    break
                        
                        filas = page.locator("div.iP2t7d, div.n5vinf, div.Fkgn4d").all()
                        
                        for fila in filas:
                            try:
                                texto_fila = fila.inner_text().strip()
                                if not texto_fila:
                                    continue
                                
                                lineas = [l.strip() for l in texto_fila.split("\n") if l.strip()]
                                hora_encontrada = None
                                es_manana = False
                                
                                for l in lineas:
                                    if "mañana" in l.lower():
                                        es_manana = True
                                        
                                    match = patron_hora.search(l)
                                    if match:
                                        hora_encontrada = match.group(0)
                                        if "mañana" in l.lower():
                                            es_manana = True
                                        break
                                        
                                if not hora_encontrada:
                                    continue
                                    
                                if es_manana:
                                    hora_encontrada = f"Mañana {hora_encontrada}"
                                
                                numero_micro = ""
                                try:
                                    badge = fila.locator("span.SJ4nDcl, span[class*='SJ4nD']").first
                                    if badge.is_visible(timeout=500):
                                        numero_micro = badge.inner_text().strip()
                                except:
                                    pass
                                    
                                if not numero_micro and len(lineas) > 0:
                                    posible = lineas[0]
                                    if len(posible) <= 4 and posible.isalnum():
                                        numero_micro = posible
                                        
                                textos_limpios = []
                                palabras_ignoradas = ["restaurantes", "hoteles", "farmacias", "cajeros", "google"]
                                for l in lineas:
                                    if "mañana" not in l.lower() and l != hora_encontrada and l != numero_micro:
                                        if not any(r in l.lower() for r in palabras_ignoradas):
                                            textos_limpios.append(l)
                                
                                destino = " ".join(textos_limpios) if textos_limpios else "Centro"
                                detalle_final = f"{numero_micro} - {destino}" if numero_micro and not destino.startswith(numero_micro) else destino
                                
                                if len(detalle_final) > 2:
                                    item = {
                                        "detalle": detalle_final,
                                        "hora": hora_encontrada
                                    }
                                    if item not in horarios_paradero:
                                        horarios_paradero.append(item)
                            except Exception:
                                continue
                                
                    except TimeoutError:
                        print(f"No se encontró panel de salidas para: {nombre_paradero}")
                    
                    paraderos_totales.append({
                        "id": f"paradero_{i + 1}",
                        "nombre": nombre_paradero,
                        "rutas": horarios_paradero
                    })
                    
                    print("Volviendo a la lista principal...")
                    page.go_back()
                    
                    try:
                        page.wait_for_selector("a.hfpxzc", state="visible", timeout=10000)
                    except TimeoutError:
                        print("Recargando la vista principal de paradas...")
                        page.goto(url, wait_until="networkidle")
                        page.wait_for_selector("a.hfpxzc", state="visible", timeout=10000)
                        
                except Exception as inner_ex:
                    print(f"Error procesando paradero: {inner_ex}")
                    page.goto(url, wait_until="networkidle")
                    page.wait_for_selector("a.hfpxzc", state="visible", timeout=10000)
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
