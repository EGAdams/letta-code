"""
LoggedProviderManager — drop-in subclass of ProviderManager that logs key
method calls to the americansjewelry.com PHP API (envelope: ProviderManager_2026).
"""

from typing import List, Optional, Union

from letta.letta_logger import LettaLogger
from letta.schemas.providers import Provider as PydanticProvider, ProviderCreate, ProviderUpdate
from letta.schemas.user import User as PydanticUser
from letta.services.provider_manager import ProviderManager

_ENVELOPE = "ProviderManager_2026"


class LoggedProviderManager(ProviderManager):
    def __init__(self) -> None:
        super().__init__()
        self._log = LettaLogger(_ENVELOPE)

    # ------------------------------------------------------------------
    # list_providers_async
    # ------------------------------------------------------------------

    async def list_providers_async(
        self,
        actor: PydanticUser,
        provider_type=None,
        name: Optional[str] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
        limit: Optional[int] = 50,
        provider_category=None,
        ascending: bool = False,
    ) -> List[PydanticProvider]:
        self._log.log("list_providers_async", "called", status="yellow")
        try:
            result = await super().list_providers_async(
                actor=actor,
                provider_type=provider_type,
                name=name,
                before=before,
                after=after,
                limit=limit,
                provider_category=provider_category,
                ascending=ascending,
            )
            self._log.log(
                "list_providers_async",
                "success",
                {"count": len(result)},
                status="green",
            )
            return result
        except Exception as exc:
            self._log.log(
                "list_providers_async",
                "error",
                {"error": str(exc)},
                status="red",
            )
            raise

    # ------------------------------------------------------------------
    # list_models_async
    # ------------------------------------------------------------------

    async def list_models_async(self, actor: PydanticUser, **kwargs):
        self._log.log("list_models_async", "called", status="yellow")
        try:
            result = await super().list_models_async(actor=actor, **kwargs)
            self._log.log(
                "list_models_async",
                "success",
                {"count": len(result)},
                status="green",
            )
            return result
        except Exception as exc:
            self._log.log(
                "list_models_async",
                "error",
                {"error": str(exc)},
                status="red",
            )
            raise

    # ------------------------------------------------------------------
    # create_provider_async
    # ------------------------------------------------------------------

    async def create_provider_async(
        self,
        request: ProviderCreate,
        actor: PydanticUser,
        is_byok: bool = True,
    ) -> PydanticProvider:
        self._log.log(
            "create_provider_async",
            "called",
            {"name": request.name},
            status="yellow",
        )
        try:
            result = await super().create_provider_async(
                request=request, actor=actor, is_byok=is_byok
            )
            self._log.log(
                "create_provider_async",
                "success",
                {"id": result.id, "name": result.name},
                status="green",
            )
            return result
        except Exception as exc:
            self._log.log(
                "create_provider_async",
                "error",
                {"error": str(exc)},
                status="red",
            )
            raise

    # ------------------------------------------------------------------
    # update_provider_async
    # ------------------------------------------------------------------

    async def update_provider_async(
        self,
        provider_id: str,
        provider_update: ProviderUpdate,
        actor: PydanticUser,
    ) -> PydanticProvider:
        self._log.log(
            "update_provider_async",
            "called",
            {"provider_id": provider_id},
            status="yellow",
        )
        try:
            result = await super().update_provider_async(
                provider_id=provider_id,
                provider_update=provider_update,
                actor=actor,
            )
            self._log.log(
                "update_provider_async",
                "success",
                {"provider_id": provider_id},
                status="green",
            )
            return result
        except Exception as exc:
            self._log.log(
                "update_provider_async",
                "error",
                {"error": str(exc)},
                status="red",
            )
            raise
