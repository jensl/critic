from __future__ import annotations

from critic import dbaccess

from .role import Role


class SubscriptionRole(Role, role_type="subscription"):
    name = "Subscription"
    table_names = {"extensionsubscriptionroles", "pubsubreservations"}

    def __init__(self, *, channel: str):
        self.channel = channel

    async def install_specific(
        self, cursor: dbaccess.TransactionCursor, role_id: int
    ) -> None:
        await cursor.insert(
            "extensionsubscriptionroles", {"role": role_id, "channel": self.channel}
        )
