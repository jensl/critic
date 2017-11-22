from critic import dbaccess

from .role import Role


class EndpointRole(Role, role_type="endpoint"):
    name = "Endpoint"
    table_names = {"extensionendpointroles"}

    def __init__(self, *, name: str):
        self.name = name

    async def install_specific(
        self, cursor: dbaccess.TransactionCursor, role_id: int
    ) -> None:
        await cursor.insert(
            "extensionendpointroles", {"role": role_id, "name": self.name}
        )
