import json
from datetime import datetime
from playwright.sync_api import sync_playwright

def extraer_horarios():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="es-CL",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        
        url = "https://www.google.com/maps/search/Maipon+esq.+Mercado+De+Chillan/@-36.6104272,-72.1013534,18z"
        print("Conectando a Google Maps para extraer datos estructurados...")
        
        horarios_extraidos = []
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(6000)
            
            print("Guardando paso_1_inicio.png...")
            page.screenshot(path="paso_1_inicio.png")
            
            print("Buscando el elemento de la parada en el mapa o panel...")
            parada_elemento = page.locator("text='Maipón'").first
            if parada_elemento.is_visible(timeout=4000):
                parada_elemento.click()
                page.wait_for_timeout(4000)

            btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
            if btn_salidas.is_visible(timeout=5000):
                btn_salidas.click()
                print("¡Clic exitoso en 'Ver el panel de salidas'!")
                page.wait_for_timeout(8000)

            print("Guardando paso_2_panel.png...")
            page.screenshot(path="paso_2_panel.png")

            # Seleccionar los contenedores individuales de cada fila de transporte en el panel lateral
            # Google Maps agrupa cada salida de micro en un contenedor de fila específico
            filas = page.locator("div.iP2t7d, div.n5vinf, div.Fkgn4d, div[jsaction]").all()
            
            print(f"=== FILAS DETECTADAS EN EL PANEL ({len(filas)}) ===")

            for idx, fila in enumerate(filas):
                try:
                    # Extraer el texto completo de la fila
                    texto_fila = fila.inner_text().strip()
                    if not texto_fila:
                        continue
                    
                    lineas = [l.strip() for l in texto_fila.split("\n") if l.strip()]
                    
                    # Buscar si en esta fila existe un patrón de hora (ej: "7:30 a.m.")
                    hora_encontrada = None
                    for l in lineas:
                        if ":" in l and ("a.m." in l.lower() or "p.m." in l.lower()):
                            hora_encontrada = l
                            break
                    
                    if not hora_encontrada:
                        continue
                        
                    # Intentar extraer específicamente el número de la micro desde el badge o textos iniciales
                    # Usamos los selectores internos de la insignia que vimos en el inspector
                    numero_micro = ""
                    try:
                        badge = fila.locator("span.SJ4nDcl, span[class*='SJ4nD']").first
                        if badge.is_visible(timeout=500):
                            numero_micro = badge.inner_text().strip()
                    except:
                        pass
                    
                    # Si no se encontró por clase específica, buscamos el primer elemento corto de la línea
                    if not numero_micro and len(lineas) > 0:
                        posible = lineas[0]
                        if len(posible) <= 4 and (posible.isalnum()):
                            numero_micro = posible
                    
                    # Extraer el destino (el texto que acompaña a la micro, omitiendo la hora y el número)
                    textos_limpios = []
                    for l in lineas:
                        if l != hora_encontrada and l != numero_micro:
                            if not any(r in l.lower() for r in ["restaurantes", "hoteles", "farmacias", "cajeros", "google"]):
                                textos_limpios.append(l)
                    
                    destino = " ".join(textos_limpios) if textos_limpios else "Centro"
                    
                    # Construir el detalle final combinando el número de micro y el destino
                    if numero_micro and not destino.startswith(numero_micro):
                        detalle_final = f"{numero_micro} - {destino}"
                    else:
                        detalle_final = destino
                        
                    if len(detalle_final) > 2:
                        item = {
                            "detalle": detalle_final,
                            "hora": hora_encontrada,
                            "empresa": "Transporte Público Chillán",
                            "precio": "$500"
                        }
                        if item not in horarios_extraidos:
                            horarios_extraidos.append(item)
                            
                except Exception as ex:
                    continue

        except Exception as e:
            print(f"Error durante la ejecución en vivo: {e}")
            
        print("Guardando paso_3_final.png...")
        page.screenshot(path="paso_3_final.png")
        browser.close()
        
        if not horarios_extraidos:
            raise ValueError("❌ Error crítico: No se pudieron extraer registros con número de micro.")
        
        print(f"¡Éxito total! Se extrajeron {len(horarios_extraidos)} registros con número de micro y horario.")
            
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M hrs")
        resultado = {
            "ciudad": "Chillán",
            "origen": "Maipón esq. Mercado De Chillán",
            "destino": "Salidas en Tiempo Real (En Vivo)",
            "actualizado_en": fecha_actual,
            "rutas": horarios_extraidos
        }
        
        with open("horarios_micros.json", "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    extraer_horarios()