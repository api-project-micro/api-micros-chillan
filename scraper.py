import json
import time
from datetime import datetime
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# 1. Definición de cuadrantes / sectores de Chillán
# Dividir por sectores garantiza capturar paraderos de la periferia (ej. Doña Francisca, Las Termas, etc.)
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
    """Cierra la ventana emergente de cookies si aparece."""
    try:
        page.locator("button:has-text('Aceptar todo'), button:has-text('Accept all')").click(timeout=3000)
    except Exception:
        pass

def hacer_scroll_completo(page):
    """Hace scroll dentro del panel lateral role='feed' hasta cargar todas las paradas del cuadrante."""
    panel_results = page.locator('div[role="feed"]')
    
    if panel_results.count() == 0:
        return

    last_height = 0
    intentos = 0
    max_intentos = 3

    while intentos < max_intentos:
        # Desplazar al final del contenedor lateral
        panel_results.evaluate("el => el.scrollTop = el.scrollHeight")
        time.sleep(2.0)  # Pausa para dar tiempo a la renderización AJAX de Google Maps
        
        new_height = panel_results.evaluate("el => el.scrollHeight")
        if new_height == last_height:
            intentos += 1
        else:
            intentos = 0
            last_height = new_height

def extraer_salidas_paradero(page):
    """Extrae las salidas/horarios de micros dentro del detalle del paradero si están disponibles."""
    salidas = []
    try:
        # Selector para las filas de líneas de transporte que muestra Google Maps
        filas = page.locator('div[data-trip-id]').all()
        for fila in filas:
            linea = fila.locator('.fontBodyMedium').first.text_content() if fila.locator('.fontBodyMedium').count() > 0 else ""
            destino = fila.locator('.fontBodySmall').first.text_content() if fila.locator('.fontBodySmall').count() > 0 else ""
            hora = fila.locator('span:has-text("p.m."), span:has-text("a.m.")').first.text_content() if fila.locator('span:has-text("p.m."), span:has-text("a.m.")').count() > 0 else ""
            
            if linea or hora:
                salidas.append({
                    "linea": linea.strip(),
                    "destino": destino.strip(),
                    "hora": hora.strip()
                })
    except Exception:
        pass
    return salidas

def ejecutar_scraper():
    paraderos_map = {}  # Diccionario para deduplicar automáticamente por URL
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-419"
        )
        page = context.new_page()

        print("=== Iniciando Scraper de Paraderos por Cuadrantes (Chillán) ===")

        for sector in CUADRANTES:
            query = f"parada de autobus {sector} Chillan"
            url_busqueda = f"https://www.google.com/maps/search/{quote(query)}"
            print(f"\n[+] Buscando en cuadrante: {sector}...")

            try:
                page.goto(url_busqueda, wait_until="networkidle", timeout=30000)
                manejar_cookies(page)
                
                # Cargar todos los elementos del panel lateral
                hacer_scroll_completo(page)

                # Obtener todas las tarjetas de resultados que son links de Maps
                enlaces_paraderos = page.locator('a[href*="/maps/place/"]').all()
                print(f"    - Encontrados en {sector}: {len(enlaces_paraderos)} tarjetas.")

                for idx, enlace in enumerate(enlaces_paraderos):
                    url = enlace.get_attribute("href")
                    nombre = enlace.get_attribute("aria-label") or enlace.text_content()

                    if not url or not nombre:
                        continue

                    # Normalización de URL básica para deduplicar correctamente
                    url_limpia = url.split("?")[0]

                    # Si el paradero ya fue registrado por otro cuadrante, omitir
                    if url_limpia in paraderos_map:
                        continue

                    # Guardar paradero
                    paraderos_map[url_limpia] = {
                        "nombre": nombre.strip(),
                        "url": url,
                        "salidas": []  # Se puede expandir haciendo click en el elemento si se requieren salidas en vivo
                    }

            except Exception as e:
                print(f"    [!] Error al procesar sector {sector}: {e}")

        browser.close()

    # 2. Formatear la lista final con IDs secuenciales
    lista_paraderos = []
    for index, (url_key, datos) in enumerate(paraderos_map.items(), start=1):
        datos["id"] = f"paradero_{index}"
        lista_paraderos.append(datos)

    # 3. Construir la estructura final del JSON
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M hrs")
    resultado_final = {
        "ciudad": "Chillán",
        "actualizado_en": fecha_actual,
        "paraderos_totales_registrados": len(lista_paraderos),
        "paraderos": lista_paraderos
    }

    # 4. Guardar en el archivo horarios_micros.json
    archivo_destino = "horarios_micros.json"
    with open(archivo_destino, "w", encoding="utf-8") as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=4)

    print(f"\n[✔] Proceso finalizado exitosamente.")
    print(f"[✔] Total de paraderos únicos registrados: {len(lista_paraderos)}")
    print(f"[✔] Archivo generado: {archivo_destino}")

if __name__ == "__main__":
    ejecutar_scraper()
