import logging

logger = logging.getLogger(__name__)

from .backend import NotFound
from .session import session


class User:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name


async def ensure(name: str) -> User:
    async with session() as backend:
        try:
            response = await backend.get("users", name=name)
        except NotFound:
            logger.info("Creating user: %s", name)
            response = await backend.post(
                "users",
                {
                    "name": name,
                    "fullname": f"{name.capitalize()} von Testing",
                    "email": f"{name}@example.org",
                    "password": "1234",
                },
            )

        return User(response["id"], name)
