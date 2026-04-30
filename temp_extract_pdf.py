import google.generativeai as genai
import os
import json

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

# Sube el PDF a Gemini
document = genai.upload_file(r"C:\Users\Bruno\Downloads\credit-statement-72172988.pdf")
model = genai.GenerativeModel('gemini-2.5-flash')

response = model.generate_content([
    document,
    "Extrae todas las transacciones financieras de este estado de cuenta. Formato estricto JSON: una lista de objetos [{\"fecha\": \"YYYY-MM-DD\", \"descripcion\": \"texto exacto\", \"monto\": -120.50}]. Usa cantidades negativas para compras/cargos y positivas para pagos/abonos."
])

# Print output enclosed in unique tags so we can regex it easily
print("===PDF_EXTRACTION_START===")
print(response.text)
print("===PDF_EXTRACTION_END===")
