# CardMovex 🚀

> Motor Inteligente de Enriquecimiento Transaccional para Tarjetas de Crédito en México.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Pydantic](https://img.shields.io/badge/Pydantic-V2-red)](https://docs.pydantic.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## ¿Qué es CardMovex?

Los agregadores como Belvo entregan transacciones de tarjeta de crédito en formato crudo: nombres de comercio truncados, comisiones sin etiquetar y categorías genéricas. **CardMovex** es la capa de inteligencia que convierte esos datos en información precisa y útil.

```
Dato crudo (Belvo):      "ANUALIDAD TRIB VISA 0012839"
Dato enriquecido:        { merchant: "BBVA", category: "Comisiones", is_commission: true, confidence: 0.99 }
```

---

## Arquitectura

```
cardmovex/
├── schemas/           # Contratos de datos Pydantic V2 (Verdad Bancaria)
├── config/            # Configuración por entorno con BaseSettings
├── processors/        # Motor de enriquecimiento IA (AsyncOpenAI + tenacity)
├── core/              # Logging estructurado (structlog)
├── tests/             # Suite completa con mocks de OpenAI
└── main.py            # FastAPI app con lifespan pattern
```

## Reglas de Ingeniería Innegociables

| Regla | Implementación |
|---|---|
| **Verdad Bancaria** | `amount`, `date`, `id` nunca pasan por el LLM |
| **Concurrencia Masiva** | `asyncio.gather` + `Semaphore(20)` — 100 movimientos en ~1s |
| **Resiliencia** | `tenacity` retry con Exponential Backoff (3 reintentos) |
| **Precisión MX** | Few-Shot Prompting con 8 ejemplos reales de bancos mexicanos |
| **Autonomía** | `confidence_score < 0.85` → `needs_review = True` automático |

---

## Fases de Desarrollo

| Fase | Descripción | Commit Tag |
|---|---|---|
| `v0.1` | Fundamentos: Schemas + Config + API básica | `fase/fundamentos` |
| `v0.2` | Concurrencia: asyncio.gather + Semaphore | `fase/concurrencia` |
| `v0.3` | Resiliencia: tenacity retry + Exponential Backoff | `fase/resiliencia` |
| `v0.4` | Precisión: Few-Shot Prompting para bancos MX | `fase/few-shot-mx` |
| `v0.5` | Observabilidad: structlog + lifespan FastAPI | `fase/observabilidad` |
| `v0.6` | Calidad: Tests con pytest + mocks OpenAI | `fase/testing` |
| `v1.0` | **Release: Sistema productizable** | `v1.0.0` |

---

## Quick Start

```bash
# 1. Clonar y entrar al proyecto
git clone https://github.com/tu-usuario/cardmovex.git
cd cardmovex

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar tu OPENAI_API_KEY

# 5. Correr el servidor
uvicorn main:app --reload
```

## Correr Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

## Endpoint Principal

```http
POST /process-movements
Content-Type: application/json

[
  {
    "id": "mov-001",
    "description_raw": "ANUALIDAD TRIB VISA BBVA",
    "amount": 899.00,
    "date": "2026-01-01"
  }
]
```

**Respuesta:**
```json
[
  {
    "id": "mov-001",
    "amount": 899.00,
    "date": "2026-01-01",
    "description_clean": "Anualidad Tarjeta Visa BBVA",
    "merchant_name": "BBVA",
    "category": "Comisiones",
    "is_commission": true,
    "is_interest": false,
    "confidence_score": 0.99,
    "needs_review": false
  }
]
```

---

## Desarrollado con estándares Senior Fintech MX 2026
