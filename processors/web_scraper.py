import asyncio
from playwright.sync_api import sync_playwright
from core.logging import get_logger

log = get_logger(__name__)

class RpScraper:
    """
    Motor RPA (Robotic Process Automation) de $0 Costo.
    Controla un navegador Chrome real para extraer datos de portales bancarios
    donde las APIs comerciales como Belvo son prohibitivas.
    """
    
    def extract_raw_movements(self, target_url: str) -> str:
        """
        Abre el portal bancario y le cede el control al usuario temporalmente
        para sortear Captchas y códigos SMS (2FA). Luego extrae el texto bruto.
        (Ejecución síncrona diseñada para correr en un Worker Thread)
        """
        log.info("rpa.scraper.starting", target_url=target_url)
        
        with sync_playwright() as p:
            # MAGIA DEMO: Si es nuestro banco de pruebas, corre 100% invisible y automático
            is_demo = "demo-bank" in target_url
            
            browser = p.chromium.launch(headless=is_demo)
            context = browser.new_context()
            page = context.new_page()
            
            page.goto(target_url)
            log.info("rpa.scraper.navigated", url=target_url)
            
            if not is_demo:
                # --- MODO ASISTIDO (Bancos Reales) ---
                # Inyectamos el botón y cedemos control al usuario por el 2FA
                page.evaluate("""
                    () => {
                        const style = document.createElement('style');
                        style.innerHTML = `
                            @keyframes rpa-pulse {
                                0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
                                70% { box-shadow: 0 0 0 15px rgba(16, 185, 129, 0); }
                                100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
                            }
                            #rpa-magic-btn {
                                position: fixed; bottom: 30px; right: 30px; z-index: 9999999;
                                padding: 22px 35px; background: rgba(16, 185, 129, 0.9);
                                backdrop-filter: blur(10px); color: white; border: 1px solid rgba(255,255,255,0.2);
                                border-radius: 20px; font-size: 18px; font-weight: 900; cursor: pointer;
                                box-shadow: 0 10px 25px rgba(0,0,0,0.4); transition: all 0.3s ease;
                                animation: rpa-pulse 2s infinite; font-family: sans-serif;
                                text-transform: uppercase; letter-spacing: 1px;
                            }
                            #rpa-magic-btn:hover { transform: scale(1.05); background: #10b981; }
                            #rpa-magic-btn:active { transform: scale(0.95); }
                        `;
                        document.head.appendChild(style);

                        const btn = document.createElement('button');
                        btn.innerHTML = '✨ EXTRAER MOVIMIENTOS CON IA';
                        btn.id = 'rpa-magic-btn';
                        document.body.appendChild(btn);
                        
                        btn.onclick = () => { 
                            btn.innerText = '⏳ PROCESANDO...'; 
                            btn.style.opacity = '0.7';
                            btn.style.pointerEvents = 'none';
                            window.__rpa_ready = true; 
                        };
                    }
                """)
                
                log.info("rpa.scraper.waiting_for_user")
                page.wait_for_function("() => window.__rpa_ready === true", timeout=300000)
            else:
                # --- MODO DEMO INVISIBLE (Full RPA) ---
                # Hacemos una micropausa para que la animación del UI se aprecie
                page.wait_for_timeout(1500)
            
            log.info("rpa.scraper.extracting_content")
            raw_text = page.evaluate("() => document.body.innerText")

            
            browser.close()
            log.info("rpa.scraper.finished", extracted_length=len(raw_text))
            
            return raw_text
