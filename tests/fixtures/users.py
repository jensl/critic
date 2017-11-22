import pytest


async def get_or_create_user(
    instance, websocket, anonymizer, name, fullname, *, admin=False
):
    user, was_created = await instance.get_or_create_user(name, fullname, admin=admin)
    if was_created:
        await websocket.pop(action="created", resource_name="users", object_id=user.id)
        await websocket.pop(
            action="created", resource_name="useremails", user_id=user.id
        )
    anonymizer.define(UserId={name: user.id})
    return user


@pytest.fixture
async def admin(instance, websocket, anonymizer):
    return await get_or_create_user(
        instance, websocket, anonymizer, "admin", "Testing Administrator", admin=True
    )


@pytest.fixture
async def alice(instance, websocket, anonymizer):
    return await get_or_create_user(
        instance, websocket, anonymizer, "alice", "Alice von Testing"
    )


@pytest.fixture
async def bob(instance, websocket, anonymizer):
    return await get_or_create_user(
        instance, websocket, anonymizer, "bob", "Bob von Testing"
    )


@pytest.fixture
async def carol(instance, websocket, anonymizer):
    return await get_or_create_user(
        instance, websocket, anonymizer, "carol", "Carol von Testing"
    )


@pytest.fixture
async def dave(instance, websocket, anonymizer):
    return await get_or_create_user(
        instance, websocket, anonymizer, "dave", "Dave von Testing"
    )
