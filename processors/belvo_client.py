"""
Paso 9 — Integración con Belvo API (Sandbox)
============================================
Este módulo encapsula toda la comunicación con la API de Belvo:
  - Autenticación (HTTP Basic Auth con Secret ID + Password)
  - Creación de un "link" (conector virtual a un banco del sandbox)
  - Extracción de transacciones del banco ficticio
  - Mapeo de la respuesta de Belvo al modelo interno CardMovementRaw

Decisión de Diseño (Senior):
  - Usamos httpx en modo async para no bloquear el event loop de FastAPI.
  - El BelvoClient es stateless; no guarda links entre requests (se pasa el link_id).
  - El SandboxSeeder crea un link de prueba de forma reproducible.
"""

import httpx
from datetime import date, timedelta
from typing import Optional

from config.settings import settings
from schemas.movements import CardMovementRaw
from core.logging import get_logger

log = get_logger(__name__)

# ── Constantes Belvo ─────────────────────────────────────────────────────────
SANDBOX_URL = "https://sandbox.belvo.com"
PRODUCTION_URL = "https://api.belvo.com"

# Institución bancaria ficticia que Belvo provee en el sandbox
SANDBOX_INSTITUTION = "erebus_mx_retail"


# Credenciales ficticias del sandbox (Belvo las acepta tal cual)
SANDBOX_USER = "bnk_test_user"
SANDBOX_PASSWORD = "full"


class BelvoClient:
    """
    Cliente HTTP async para la API REST de Belvo.

    Uso:
        async with BelvoClient() as client:
            link_id = await client.create_sandbox_link()
            movements = await client.get_transactions(link_id)
    """

    def __init__(self):
        base_url = (
            SANDBOX_URL
            if settings.BELVO_ENVIRONMENT == "sandbox"
            else PRODUCTION_URL
        )
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=(settings.BELVO_SECRET_ID, settings.BELVO_SECRET_PASSWORD),
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    # ── Links ──────────────────────────────────────────────────────────────

    async def create_sandbox_link(self) -> str:
        """
        Crea (o reutiliza) un 'link' ficticio al banco de sandbox.
        Un link = conector autorizado entre CardMovex y una cuenta bancaria.

        Returns:
            link_id (str): UUID del link creado en Belvo.
        """
        log.info("belvo.create_link.start", institution=SANDBOX_INSTITUTION)

        payload = {
            "institution": SANDBOX_INSTITUTION,
            "username": SANDBOX_USER,
            "password": SANDBOX_PASSWORD,
            "access_mode": "single",  # 'single' para sandbox/demo, 'recurrent' para producción
        }

        response = await self._client.post("/api/links/", json=payload)

        # Log the raw response for debugging
        log.warning(
            "belvo.create_link.response",
            status=response.status_code,
            body=response.text[:500],
        )

        # Si ya existe un link para esta institución, Belvo devuelve 400 con el link_id
        if response.status_code in (400, 409):
            try:
                error_data = response.json()
                errors = error_data if isinstance(error_data, list) else [error_data]
                for err in errors:
                    meta = err.get("meta", {}) or {}
                    if meta.get("link_id"):
                        existing = meta["link_id"]
                        log.info("belvo.create_link.reused", link_id=existing)
                        return existing
            except Exception:
                pass

        try:
            response.raise_for_status()
            link_id = response.json()["id"]
            log.info("belvo.create_link.created", link_id=link_id)
            return link_id
        except Exception as e:
            log.error("belvo.create_link.error_fallback", error=str(e))
            # Fallback de DEMO: Si el sandbox falla, devolvemos un link dummy
            return "dummy-link-sandbox-fallback"


    # ── Transacciones ──────────────────────────────────────────────────────

    async def get_transactions(
        self,
        link_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> list[CardMovementRaw]:
        """
        Extrae transacciones bancarias de un link y las mapper al
        esquema interno CardMovementRaw para que el TextEnricher las procese.

        Args:
            link_id: UUID del link de Belvo.
            date_from: Fecha inicio (default: hace 30 días).
            date_to: Fecha fin (default: hoy).

        Returns:
            Lista de CardMovementRaw listos para enriquecer con IA.
        """
        date_from = date_from or (date.today() - timedelta(days=30))
        date_to = date_to or date.today()

        # Check if keys are loaded
        if not settings.BELVO_SECRET_ID or not settings.BELVO_SECRET_PASSWORD:
            log.error("belvo.api.missing_credentials")
            raise Exception("No se encontraron BELVO_SECRET_ID o PASSWORD en el archivo .env")

        try:
            # Reutilizar o crear link
            link_id = await self.create_sandbox_link()
            
            log.info("belvo.get_transactions.start", link_id=link_id)
            params = {"link": link_id}
            if date_from: params["value_date__gte"] = date_from.isoformat()
            if date_to: params["value_date__lte"] = date_to.isoformat()

            response = await self._client.get("/api/transactions/", params=params)
            
            # Si es un error de autenticación, NO queremos fallback silencioso
            if response.status_code in (401, 403):
                log.error("belvo.auth_error", status=response.status_code, body=response.text)
                raise Exception(f"Error de Autenticación con Belvo ({response.status_code}): Verifica tus llaves en el .env")

            response.raise_for_status()
            raw_transactions = response.json()
            
            log.info("belvo.get_transactions.done", count=len(raw_transactions))
            return [_map_belvo_to_raw(tx) for tx in raw_transactions]

        except Exception as e:
            log.error("belvo.api_error", error=str(e), exc_info=True)
            raise e




# ── Mapper de Belvo → Esquema Interno ──────────────────────────────────────

def _map_belvo_to_raw(tx: dict) -> CardMovementRaw:
    """
    Convierte una transacción cruda de Belvo al modelo CardMovementRaw.

    Belvo devuelve campos como:
        id, description, amount, value_date, category, merchant.name
    """
    return CardMovementRaw(
        id=tx["id"],
        description_raw=tx.get("description") or "SIN DESCRIPCION",
        amount=float(tx.get("amount", 0.0)),
        date=date.fromisoformat(tx.get("value_date", str(date.today()))),
        category_raw=tx.get("category"),
        merchant_raw=(
            tx.get("merchant", {}) or {}
        ).get("name") if tx.get("merchant") else None,
    )
