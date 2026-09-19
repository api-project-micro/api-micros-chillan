import json
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

# 1. Definición de los 4 cuadrantes geográficos de Chillán
SECTORES = [
    {
        "id": 0,
        "nombre": "Cuadrante 1: Nororiente",
        "url": "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.5950,-72.0850,14z"
    },
    {
        "id": 1,
        "nombre": "Cuadrante 2: Norponiente",
        "url": "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.5950,-72.1250,14z"
    },
    {
        "id": 2,
        "nombre": "Cuadrante 3: Surponiente",
        "url": "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.6300,-72.1250,14z"
    },
    {
        "id": 3,
        "nombre": "Cuadrante 4: Suroriente",
        "url": "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.6300,-72.0850,14z"
    }
]

def obtener_siguiente_sector():
    """Lee el estado actual y retorna el índice del sector a procesar."""
    archivo_estado = "estado_scraper.json"
    if os.path.exists(archivo_estado):
        try:
            with open(archivo_estado, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("siguiente_sector", 0) % len(SECTORES)
        except Exception:
            return 0
    return 0

def guardar_estado_siguiente(sector_actual):
    """Guarda el puntero al próximo sector para la siguiente ejecución."""
    siguiente = (sector_actual + 1) % len(SECTORES)
    with open("estado_scraper.json", "w", encoding="utf-8") as f:
        json.dump({"siguiente_sector": siguiente}, f, indent=4)

def cargar_datos_existentes():
    """Carga los paraderos guardados previamente para fusionar datos."""
    archivo = "horarios_micros.json"
    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"ciudad": "Chillán", "actualizado_en": "", "paraderos": []}

def extraer_todos_los_paraderos():
    idx_sector = obtener_siguiente_sector()
    sector_info = SECTORES[idx_sector]
    
    print(f"=== INICIANDO EXTRACCIÓN ===")
    print(f"Ejecutando: {sector_info['nombre']} (Sector {idx_sector + 1}/{len(SECTORES)})")
    
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
        
        paraderos_sector = []
        patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
        patron_linea = re.compile(r'^\d+[A-Za-z0-9]*$')
        
        try:
            page.goto(sector_info["url"], wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            
            try:
                page.wait_for_selector("a.hfpxzc", state="visible", timeout=20000)
            except TimeoutError:
                print(f"No se encontraron paraderos en {sector_info['nombre']}.")
                guardar_estado_siguiente(idx_sector)
                return

            # =========================================================
            # FASE 1: Scroll continuo e infinito para capturar URLs
            # =========================================================
            print("Cargando lista del sector con scroll dinámico...")
            
            intentos_sin_cambio = 0
            urls_paraderos = []
            
            while intentos_sin_cambio < 4:
                page.evaluate("""
                    const feed = document.querySelector('div[role="feed"]');
                    if (feed) { feed.scrollBy(0, 3000); }
                """)
                page.wait_for_timeout(1500)
                
                elementos = page.locator("a.hfpxzc").all()
                nuevas_urls = [el.get_attribute("href") for el in elementos if el.get_attribute("href")]
                
                for u in nuevas_urls:
                    if u not in urls_paraderos:
                        urls_paraderos.append(u)
                
                print(f"Paraderos detectados en este sector: {len(urls_paraderos)}")
                
                if page.locator("text='Has llegado al final de la lista'").is_visible():
                    print("Fin de la lista del cuadrante.")
                    break
                    
                if len(nuevas_urls) == len(urls_paraderos):
                    intentos_sin_cambio += 1
                else:
                    intentos_sin_cambio = 0

            print(f"\n=== TOTAL PARADEROS EN {sector_info['nombre'].upper()}: {len(urls_paraderos)} ===")

            # =========================================================
            # FASE 2: Procesar paraderos del cuadrante
            # =========================================================
            for i, url_paradero in enumerate(urls_paraderos):
                try:
                    print(f"[{i + 1}/{len(urls_paraderos)}] Extrayendo...")
                    page.goto(url_paradero, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                    
                    h1 = page.locator("h1").first
                    nombre_paradero = h1.inner_text() if h1.is_visible() else f"Paradero {i + 1}"
                    
                    salidas_programadas = []
                    btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
                    
                    if btn_salidas.is_visible(timeout=2500):
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
                    
                    paraderos_sector.append({
                        "nombre": nombre_paradero,
                        "url": url_paradero,
                        "salidas": salidas_programadas
                    })

                except Exception as inner_ex:
                    print(f"Error en paradero {i + 1}: {inner_ex}")
                    continue

        except Exception as e:
            print(f"Error general durante la ejecución: {e}")
        finally:
            browser.close()
            
        # =========================================================
        # FASE 3: Fusión incremental de datos con el JSON existente
        # =========================================================
        datos_globales = cargar_datos_existentes()
        mapa_paraderos = {p.get("url", p.get("nombre")): p for p in datos_globales.get("paraderos", [])}
        
        # Actualizar o agregar los paraderos capturados en este cuadrante
        for p_nuevo in paraderos_sector:
            clave = p_nuevo["url"]
            mapa_paraderos[clave] = p_nuevo
            
        lista_combinada = list(mapa_paraderos.values())
        
        # Re-indexar IDs
        for idx, p_item in enumerate(lista_combinada):
            p_item["id"] = f"paradero_{idx + 1}"

        resultado_final = {
            "ciudad": "Chillán",
            "actualizado_en": datetime.now().strftime("%Y-%m-%d %H:%M hrs"),
            "paraderos_totales_registrados": len(lista_combinada),
            "paraderos": lista_combinada
        }
        
        with open("horarios_micros.json", "w", encoding="utf-8") as f:
            json.dump(resultado_final, f, ensure_ascii=False, indent=4)
            
        # Guardar qué cuadrante ejecutar en la siguiente ronda
        guardar_estado_siguiente(idx_sector)
        
        siguiente_cuadrante = SECTORES[(idx_sector + 1) % len(SECTORES)]["nombre"]
        print(f"\n¡Éxito! Se procesó el '{sector_info['nombre']}'.")
        print(f"Base acumulada total: {len(lista_combinada)} paraderos en 'horarios_micros.json'.")
        print(f"Próxima ejecución escaneará: '{siguiente_cuadrante}'.")

if __name__ == "__main__":
    extraer_todos_los_paraderos()
