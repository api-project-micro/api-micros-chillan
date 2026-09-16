# URL exacta proporcionada con tus coordenadas
        url = "https://www.google.com/maps/search/Parada+de+autob%C3%BAs/@-36.6004151,-72.0997396,18z?entry=ttu&g_ep=EgoyMDI2MDkxMy4wIKXMDSoASAFQAw%3D%3D"
        print("Conectando a Google Maps con el enlace directo de paraderos...")
        
        paraderos_totales = []
        patron_hora = re.compile(r'\b\d{1,2}:\d{2}(?:\s?[aApP]\.?\s?[mM]\.?)?\b')
        
        try:
            # Cambiamos networkidle por domcontentloaded para evitar timeouts por conexiones en segundo plano
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            # Damos unos segundos adicionales para que renderice la interfaz de resultados
            page.wait_for_timeout(5000)
            
            try:
                page.wait_for_selector("a.hfpxzc", state="visible", timeout=20000)
            except TimeoutError:
                print("No se pudieron cargar los resultados iniciales de paraderos.")
                return
            
            resultados_paradas = page.locator("a.hfpxzc").all()
            print(f"=== PARADAS DETECTADAS: {len(resultados_paradas)} ===")
