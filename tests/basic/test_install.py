import pytest

from ..fixtures.api import API
from ..fixtures.websocket import WebSocket
from ..fixtures.instance import User
from ..fixtures.repository import CriticRepository
from ..fixtures import Snapshot
from ..utilities import Anonymizer, execute, raise_for_status


@pytest.mark.asyncio
async def test_install(
    api: API,
    admin: User,
    alice: User,
    bob: User,
    carol: User,
    dave: User,
    anonymizer,
    snapshot: Snapshot,
):
    snapshot.assert_match(
        anonymizer(raise_for_status(await api.get("users"))), "all users"
    )

    async with api.session(admin) as as_admin:
        snapshot.assert_match(
            anonymizer(
                raise_for_status(
                    await as_admin.get("sessions/current", include=("users",))
                )
            ),
            "as admin",
        )

    async with api.session(alice) as as_alice:
        snapshot.assert_match(
            anonymizer(
                raise_for_status(
                    await as_alice.get("sessions/current", include=("users",))
                )
            ),
            "as alice",
        )


@pytest.mark.asyncio
async def test_empty_repo(empty_repo, anonymizer, snapshot):
    snapshot.assert_match(
        anonymizer(
            raise_for_status(
                await execute("git ls-remote", "git", "ls-remote", empty_repo.url)
            )
        )
    )


@pytest.mark.asyncio
async def test_critic_repo(websocket, critic_repo, snapshot):
    assert critic_repo.name == "test_critic_repo"
