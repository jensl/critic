from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

from .request import Request
from critic import api
from critic import extensions
from critic.gitaccess import SHA1


@dataclass
class ReadManifestResult:
    filename: str
    source: str

    def __repr__(self) -> str:
        return (
            f"ReadManifestResult(filename={self.filename}, "
            f"source=<{len(self.source)} chars>)"
        )

    def read_manifest(self) -> extensions.manifest.Manifest:
        manifest = extensions.manifest.Manifest(
            filename=self.filename, source=self.source
        )
        manifest.read()
        return manifest


@dataclass
class ReadManifest(Request[ReadManifestResult]):
    extension_id: int
    version_name: Optional[str]
    sha1: Optional[SHA1]

    async def dispatch(self, critic: api.critic.Critic) -> ReadManifestResult:
        extension = await api.extension.fetch(critic, self.extension_id)
        low_level = await extension.low_level
        if not low_level:
            raise Exception("Extension is not available")
        manifest = await low_level.getManifest(self.version_name, sha1=self.sha1)
        assert manifest.filename
        assert manifest.source
        return ReadManifestResult(manifest.filename, manifest.source)


async def read_manifest(
    version: api.extensionversion.ExtensionVersion,
) -> extensions.manifest.Manifest:
    extension = await version.extension
    result = await ReadManifest(extension.id, version.name, version.sha1).issue()
    return result.read_manifest()
