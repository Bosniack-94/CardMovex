# Project: CardMovex

## Objetivos
Sistema modular Core Bancario/Fintech que consume datos crudos de tarjetas de crédito (ej. extraídos de Belvo) y utiliza IA para limpiarlos, categorizarlos y estructurarlos manteniendo la Verdad Bancaria intacta.

## Comandos Principales (FastAPI)
- **Desarrollo**: `uvicorn main:app --reload`
- **Dependencias necesarias**: `pip install fastapi uvicorn pydantic pydantic-settings openai python-dotenv`

## Arquitectura (Capa L1 - Estructura Senior)
- `/schemas/`: Modelos de datos Pydantic para tipado estricto (Verdad Bancaria y Contratos de Datos).
- `/config/`: Variables de entorno, thresholds e inyección de dependencias.
- `/processors/`: Lógica de enriquecimiento con IA usando OpenAI (gpt-4o-mini).
- `/main.py`: Punto de entrada unificado y enrutador principal de FastAPI.

## Reglas de Oro AI (Gotchas)
- **Verdad Bancaria**: JAMÁS modificar `amount` ni `date` en la lógica de IA. Se pasan directamente al objeto final.
- **Autonomía**: Todo movimiento tiene un `confidence_score`. Si baja del `0.85` de la configuración (o el threshold en turno), se marca automáticamente `needs_review = True`.
- **Patrones MX**: El prompt de IA contempla estructuras bancarias mexicanas (BBVA, Banorte, Santander, etc.) y detecta sus comisiones escondidas de forma proactiva.
