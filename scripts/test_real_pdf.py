import os
import sys
import json
import argparse
from dotenv import load_dotenv
import google.generativeai as genai
from rich.console import Console
from rich.table import Table

# Cargar variables de entorno
load_dotenv()
console = Console()

def main():
    parser = argparse.ArgumentParser(description="CardMovex - Lector de Estados de Cuenta PDF usando IA Multimodal")
    parser.add_argument("pdf_path", help="Ruta absoluta al archivo PDF del Estado de Cuenta")
    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        console.print(f"[bold red]Error:[/bold red] No se encontró el archivo: {args.pdf_path}")
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error crítico:[/bold red] GEMINI_API_KEY no configurado en .env")
        sys.exit(1)

    genai.configure(api_key=api_key)

    with console.status(f"[bold cyan]Subiendo PDF al motor de Inteligencia Artificial (Multimodal)...", spinner="dots"):
        try:
            document = genai.upload_file(args.pdf_path)
        except Exception as e:
            console.print(f"[bold red]Error subiendo el archivo: {e}[/bold red]")
            sys.exit(1)

    with console.status("[bold green]Analizando transacciones bancarias usando Gemini 2.5 Flash...", spinner="dots"):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            prompt = (
                "Eres un auditor financiero experto. Extrae TODAS las transacciones bancarias de este estado de cuenta. "
                "Devuelve ÚNICAMENTE un arreglo JSON válido sin bloques markdown, con la siguiente estructura estricta: "
                '[{"fecha": "YYYY-MM-DD", "comercio": "texto exacto", "monto": -120.50}]. '
                "Usa cantidades negativas para compras/cargos y positivas para pagos/abonos. Nada de texto extra."
            )
            response = model.generate_content([document, prompt])
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            
            # Limpiar posible basura del modelo
            start_idx = raw_text.find('[')
            end_idx = raw_text.rfind(']') + 1
            if start_idx != -1 and end_idx != -1:
                clean_json_str = raw_text[start_idx:end_idx]
                transactions = json.loads(clean_json_str)
            else:
                raise ValueError("El modelo no devolvió un JSON válido.")

        except Exception as e:
            console.print(f"[bold red]Error de análisis LLM:[/bold red] {e}")
            console.print("Respuesta cruda:")
            console.print(response.text if 'response' in locals() else "N/A")
            sys.exit(1)

    # Mostrar tabla espectacular
    table = Table(title="Transacciones Extraídas del PDF Oficial", header_style="bold magenta")
    table.add_column("Fecha", style="cyan", justify="center")
    table.add_column("Comercio Extraído", style="white")
    table.add_column("Monto (MXN)", justify="right")

    for t in transactions:
        monto = float(t.get("monto", 0))
        color = "green" if monto >= 0 else "red"
        monto_str = f"[{color}]${abs(monto):,.2f}[/{color}]"
        signo = "+" if monto >= 0 else "-"
        table.add_row(t.get("fecha", ""), t.get("comercio", ""), f"[{color}]{signo}${abs(monto):,.2f}[/{color}]")

    console.print("\n")
    console.print(table)
    console.print(f"\n[bold yellow]Total de movimientos procesados: {len(transactions)}[/bold yellow]\n")

if __name__ == "__main__":
    main()
