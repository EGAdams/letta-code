"""
LoggedUserManager — drop-in subclass of UserManager that logs key method calls
to the americansjewelry.com PHP API (envelope: UserManager_2026).
"""

from typing import List, Optional

from letta.letta_logger import LettaLogger
from letta.schemas.user import User as PydanticUser
from letta.services.user_manager import UserManager

_ENVELOPE = "UserManager_2026"


class LoggedUserManager(UserManager):
    def __init__(self) -> None:
        super().__init__()
        self._log = LettaLogger(_ENVELOPE)

    # ------------------------------------------------------------------
    # get_default_actor_async
    # ------------------------------------------------------------------

    async def get_default_actor_async(self) -> PydanticUser:
        self._log.log("get_default_actor_async", "called", status="yellow")
        try:
            result = await super().get_default_actor_async()
            self._log.log(
                "get_default_actor_async",
                "success",
                {"user_id": result.id},
                status="green",
            )
            return result
        except Exception as exc:
            self._log.log(
                "get_default_actor_async",
                "error",
                {"error": str(exc)},
                status="red",
            )
            raise

    # ------------------------------------------------------------------
    # get_actor_by_id_async
    # ------------------------------------------------------------------

    async def get_actor_by_id_async(self, actor_id: str) -> PydanticUser:
        self._log.log(
            "get_actor_by_id_async",
            "called",
            {"actor_id": actor_id},
            status="yellow",
        )
        try:
            result = await super().get_actor_by_id_async(actor_id=actor_id)
            self._log.log(
                "get_actor_by_id_async",
                "success",
                {"user_id": result.id},
                status="green",
            )
            return result
        except Exception as exc:
            self._log.log(
                "get_actor_by_id_async",
                "error",
                {"error": str(exc)},
                status="red",
            )
            raise

    # ------------------------------------------------------------------
    # get_actor_or_default_async
    # ------------------------------------------------------------------

    async def get_actor_or_default_async(
        self, actor_id: Optional[str] = None
    ) -> PydanticUser:
        self._log.log(
            "get_actor_or_default_async",
            "called",
            {"actor_id": actor_id},
            status="yellow",
        )
        try:
            result = await super().get_actor_or_default_async(actor_id=actor_id)
            self._log.log(
                "get_actor_or_default_async",
                "success",
                {"user_id": result.id},
                status="green",
            )
            return result
        except Exception as exc:
            self._log.log(
                "get_actor_or_default_async",
                "error",
                {"error": str(exc)},
                status="red",
            )
            raise

    # ------------------------------------------------------------------
    # list_actors_async
    # ------------------------------------------------------------------

    async def list_actors_async(
        self,
        after: Optional[str] = None,
        limit: Optional[int] = 50,
    ) -> List[PydanticUser]:
        self._log.log("list_actors_async", "called", status="yellow")
        try:
            result = await super().list_actors_async(after=after, limit=limit)
            self._log.log(
                "list_actors_async",
                "success",
                {"count": len(result)},
                status="green",
            )
            return result
        except Exception as exc:
            self._log.log(
                "list_actors_async",
                "error",
                {"error": str(exc)},
                status="red",
            )
            raise
