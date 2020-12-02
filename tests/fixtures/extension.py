from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
import pytest
import shutil
import tempfile
from typing import Any, AsyncIterator, Dict, Protocol, TypedDict, Union, cast

from . import Request
from .instance import User
from .frontend import Frontend, FrontendResponse
from .api import API
from .websocket import WebSocket
from ..utilities import Anonymizer, AccessToken, generate_name, git, raise_for_status


class ExtensionData(TypedDict):
    id: int
    name: str


class ExtensionVersionData(TypedDict):
    id: int
    sha1: str


class ExtensionInstallationData(TypedDict):
    id: int


class ExtensionFrontend:
    def __init__(self, frontend: Frontend, full_name: str):
        self.frontend = frontend
        self.full_name = full_name
        self.prefix = f"api/x/{full_name}/endpoint"

    async def get(
        self, endpoint: str, path: str, *, params: Dict[str, Any] = {}
    ) -> FrontendResponse:
        return await self.frontend.get(
            f"{self.prefix}/{endpoint}/{path}", params=params
        )

    async def post(
        self, endpoint: str, path: str, body: object, *, params: Dict[str, Any] = {}
    ) -> FrontendResponse:
        if not isinstance(body, (bytes, str)):
            body = json.dumps(body)
        return await self.frontend.post(
            f"{self.prefix}/{endpoint}/{path}", body, params=params
        )

    async def put(
        self, endpoint: str, path: str, body: object, *, params: Dict[str, Any] = {}
    ) -> FrontendResponse:
        if not isinstance(body, (bytes, str)):
            body = json.dumps(body)
        return await self.frontend.put(
            f"{self.prefix}/{endpoint}/{path}", body, params=params
        )

    async def delete(
        self, endpoint: str, path: str, *, params: Dict[str, Any] = {}
    ) -> FrontendResponse:
        return await self.frontend.delete(
            f"{self.prefix}/{endpoint}/{path}", params=params
        )

    @asynccontextmanager
    async def session(
        self, user: Union[User, AccessToken]
    ) -> AsyncIterator[ExtensionFrontend]:
        async with self.frontend.session(user) as session:
            yield ExtensionFrontend(session, self.full_name)


class Extension(ExtensionFrontend):
    data: ExtensionData
    version_data: ExtensionVersionData
    installation_data: ExtensionInstallationData

    def __init__(
        self,
        frontend: Frontend,
        api: API,
        websocket: WebSocket,
        admin: User,
        anonymizer: Anonymizer,
        name: str,
        url: str,
        snapshot: bool,
    ):
        self.api = api
        self.websocket = websocket
        self.admin = admin
        self.anonymizer = anonymizer
        self.name = name
        self.url = url
        self.snapshot = snapshot

        super().__init__(frontend, generate_name(name))

    async def expect_message(self, channel: str, **checks: Any) -> None:
        if self.snapshot:
            await self.websocket.expect(channel, **checks)
        else:
            await self.websocket.pop(channel, **checks)

    async def install(self, publisher: User, install_for: User = None) -> None:
        async with self.api.session(publisher) as as_publisher:
            self.data = cast(
                ExtensionData,
                await as_publisher.create(
                    self.name,
                    "extensions",
                    {"name": self.full_name, "system": True, "url": self.url},
                    query={"fields": "-versions"},
                ),
            )

            self.version_data = cast(
                ExtensionVersionData,
                await as_publisher.fetch(
                    self.name,
                    f"extensions/{self.data['id']}/extensionversions",
                    attributes=("id", "sha1"),
                ),
            )

        installer = self.admin if install_for is None else install_for

        async with self.api.session(installer) as as_installer:
            self.installation_data = cast(
                ExtensionInstallationData,
                await as_installer.create(
                    self.name,
                    "extensioninstallations",
                    {
                        "extension": self.data["id"],
                        "version": self.version_data["id"],
                        "universal": install_for is None,
                    },
                    ExtensionId="$.request.payload.extension",
                    ExtensionVersionId="$.request.payload.version",
                ),
            )

        await self.expect_message(
            "extensions",
            action="created",
            resource_name="extensions",
            object_id=self.data["id"],
        )

        await self.expect_message(
            "extensioninstallations",
            action="created",
            resource_name="extensioninstallations",
            object_id=self.installation_data["id"],
        )

    async def cleanup(self) -> None:
        async with self.api.session(self.admin) as as_admin:
            raise_for_status(
                await as_admin.delete(
                    f"extensioninstallations/{self.installation_data['id']}"
                )
            )
            raise_for_status(await as_admin.delete(f"extensions/{self.data['id']}"))

        await self.expect_message(
            f"extensions/{self.data['id']}",
            action="deleted",
            resource_name="extensions",
            object_id=self.data["id"],
        )

        await self.expect_message(
            f"extensioninstallations/{self.installation_data['id']}",
            action="deleted",
            resource_name="extensioninstallations",
            object_id=self.installation_data["id"],
        )


class CreateExtension(Protocol):
    @asynccontextmanager
    def __call__(self, name: str, url: str) -> AsyncIterator[Extension]:
        ...


@pytest.fixture
def create_extension(
    request: Request,
    frontend: Frontend,
    api: API,
    websocket: WebSocket,
    admin: User,
    anonymizer: Anonymizer,
) -> CreateExtension:
    marker = request.node.get_closest_marker("enable_snapshot")
    snapshot = "extension" in marker.args if marker else False

    @asynccontextmanager
    async def create_extension(
        name: str, url: str, *, publisher: User = None, install_for: User = None
    ) -> AsyncIterator[Extension]:
        extension = Extension(
            frontend, api, websocket, admin, anonymizer, name, url, snapshot
        )
        anonymizer.replace_string(url, f"git://extensions/{name}.git")
        if publisher is None:
            publisher = admin
        await extension.install(publisher, install_for)
        try:
            yield extension
        finally:
            await extension.cleanup()

    return create_extension


@pytest.fixture
async def test_extension(
    workdir: str, create_extension: CreateExtension
) -> AsyncIterator[Extension]:
    with tempfile.TemporaryDirectory(dir=workdir) as base_dir:
        path = os.path.join(base_dir, "test_extension")
        shutil.copytree(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../extensions/test_extension")
            ),
            path,
        )
        raise_for_status(await git("init", cwd=path))
        raise_for_status(await git("add", ".", cwd=path))
        raise_for_status(await git("commit", "-mInitial", cwd=path))
        async with create_extension(
            "test-extension", f"file://{os.path.abspath(path)}"
        ) as test_extension:
            yield test_extension
