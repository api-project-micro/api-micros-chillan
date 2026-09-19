import json
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuración de los 4 cuadrantes geográficos de Chillán
CUADRANTES = [
    {
        "id": "1",
        "nombre": "Cuadrante 1: Nororiente",
        "sector": "Vicente Pérez / Purén / Alonso de Ercilla Norte",
        "url": "https://www.google.com/maps/search/Parada+de+autob%C3%BAs+cerca+de+-36.5900,+-72.0750"
    },
    {
        "id": "2",
        "nombre": "Cuadrante 2: Norponiente",
        "sector": "Paul Harris / Av. Ecuador / Parque Lantaño",
        "url": "https://www.google.com/maps/search/Parada+de+autob%C3%BAs+cerca+de+-36.5900,+-72.1250"
    },
    {
        "id": "3",
        "nombre": "Cuadrante 3: Surponiente",
        "sector": "Centro / Maipón / Chillán Viejo",
        "url": "https://www.google.com/maps/search/Parada+de+autob%C3%BAs+cerca+de+-36.6300,+-72.1250"
    },
    {
        "id": "4",
        "nombre": "Cuadrante 4: Suroriente",
        "sector": "Los Volcanes / Mapuches / Alonso de Ercilla Sur",
        "url": "https://www.google.com/maps/search/Parada+de+autob%C3%BAs+cerca+de+-36.6300,+-72.0750"
    }
]

def extraer_horarios_todos_cuadrantes():
    resultado_global = {
        "ciudad": "Chillán",
        "actualizado_en": datetime.now().strftime("%Y-%m-%d %H:%M hrs"),
        "cuadrantes": []
    }

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

        for cuadrante in CUADRANTES:
            print(f"\n==================================================")
            print(f" PROCESANDO: {cuadrante['nombre']}")
            print(f" Sector: {cuadrante['sector']}")
            print(f"==================================================")
            
            horarios_cuadrante = []
            
            try:
                page.goto(cuadrante["url"], wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(5000)
                
                # Seleccionar primera parada visible en la lista del sector
                primera_parada = page.locator("div[role='feed'] a[aria-label], div.a4E33c").first
                if primera_parada.is_visible(timeout=5000):
                    print("  -> Clic en parada detectada...")
                    primera_parada.click()
                    page.wait_for_timeout(4000)

                # Desplegar panel de salidas en vivo
                btn_salidas = page.locator("button:has-text('Ver el panel de salidas'), div[role='button']:has-text('Ver el panel de salidas')").first
                if btn_salidas.is_visible(timeout=5000):
                    btn_salidas.click()
                    print("  -> Desplegando panel de salidas...")
                    page.wait_for_timeout(6000)

                # Extraer las filas de transporte
                filas = page.locator("div.iP2t7d, div.n5vinf, div.Fkgn4d, div[jsaction]").all()
                print(f"  -> Filas encontradas: {len(filas)}")

                for fila in filas:
                    try:
                        texto_fila = fila.inner_text().strip()
                        if not texto_fila:
                            continue
                        
                        lineas = [l.strip() for l in texto_fila.split("\n") if l.strip()]
                        
                        # Buscar patrón de hora
                        hora_encontrada = None
                        for l in lineas:
                            if ":" in l and ("a.m." in l.lower() or "p.m." in l.lower()):
                                hora_encontrada = l
                                break
                        
                        if not hora_encontrada:
                            continue
                            
                        # Identificar número de micro
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
                        
                        # Limpieza de etiquetas accesorias
                        textos_limpios = [
                            l for l in lineas 
                            if l != hora_encontrada and l != numero_micro and not any(
                                r in l.lower() for r in ["restaurantes", "hoteles", "farmacias", "cajeros", "google"]
                            )
                        ]
                        
                        destino = " ".join(textos_limpios) if textos_limpios else cuadrante["nombre"]
                        
                        # Detalle consolidado
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
                            if item not in horarios_cuadrante:
                                horarios_cuadrante.append(item)
                                print(f"     [+] {detalle_final} | {hora_encontrada}")
                                
                    except Exception:
                        continue

            except Exception as e:
                print(f"  ⚠️ Error en {cuadrante['nombre']}: {e}")
            
            # Registrar el cuadrante procesado
            resultado_global["cuadrantes"].append({
                "id": cuadrante["id"],
                "nombre": cuadrante["nombre"],
                "sector": cuadrante["sector"],
                "total_rutas": len(horarios_cuadrante),
                "rutas": horarios_cuadrante
            })

        browser.close()

    # Guardar archivo consolidado
    with open("horarios_micros_chillan.json", "w", encoding="utf-8") as f:
        json.dump(resultado_global, f, ensure_ascii=False, indent=4)

    total_registros = sum(c["total_rutas"] for c in resultado_global["cuadrantes"])
    print(f"\n==================================================")
    print(f" PROCESO COMPLETADO EXITOSAMENTE")
    print(f" Total de rutas extraídas: {total_registros}")
    print(f" Archivo guardado: horarios_micros_chillan.json")
    print(f"==================================================")

if __name__ == "__main__":
    extraer_horarios_todos_cuadrantes()
