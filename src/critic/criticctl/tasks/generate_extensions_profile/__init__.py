# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol, Set

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess
from critic.background.extensiontasks import fetch_from_external
from critic.extensions.manifest import ManifestError
from critic.gitaccess import SHA1
from critic import extensions
from ...utils import fail
from .autocommit import autocommit, current_sha1

name = "generate-extensions-profile"
description = "Generate extensions profile"


class Arguments(Protocol):
    extensions_dir: str
    autocommit: bool
    discover: bool


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--autocommit", action="store_true")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("extensions_dir")


@dataclass
class ExtensionInfo:
    source_dir: Path

    name: str
    version_name: str
    version_sha1: SHA1
    manifest: extensions.manifest.Manifest
    uiaddon: bool

    extension: Optional[api.extension.Extension] = None
    version: Optional[api.extensionversion.ExtensionVersion] = None


async def process_extension(arguments: Arguments, source_dir: Path) -> ExtensionInfo:
    async with gitaccess.GitRepository.direct(str(source_dir)) as repository:
        if arguments.autocommit:
            (version_name, sha1) = await autocommit(source_dir, repository)
        else:
            (version_name, sha1) = await current_sha1(repository)
        extension = extensions.extension.Extension(
            None, str(source_dir), None, source_dir.name, repository
        )
        try:
            manifest = await extension.getManifest(sha1=sha1)
        except ManifestError as error:
            fail(f"{source_dir}: invalid manifest:\n  {error}")

    return ExtensionInfo(
        source_dir,
        manifest.name,
        version_name,
        sha1,
        manifest,
        (source_dir / "uiaddon").is_dir(),
    )


async def ensure_extension(
    transaction: api.transaction.Transaction, info: ExtensionInfo
) -> None:
    logger.info("Resolving extension: %s", info.name)

    url = f"file://{info.source_dir.resolve()}"

    try:
        info.extension = await api.extension.fetch(transaction.critic, key=info.name)
        logger.info("- found existing extension: id=%d", info.extension.id)

        if info.extension.url != url:
            logger.info("- updating extension URL: %s -> %s", info.extension.url, url)
            modifier = await transaction.modifyExtension(info.extension)
            await modifier.setURL(url)

        logger.info("- updating extension: source=%s", info.source_dir)
        await fetch_from_external(transaction.critic, info.extension)

        return
    except api.extension.Error:
        pass

    info.extension = (await transaction.createExtension(info.name, url)).subject
    logger.info("- created new extension: id=%d", info.extension.id)


async def ensure_version(
    transaction: api.transaction.Transaction, info: ExtensionInfo
) -> None:
    logger.info("Resolving extension version: %s :: %s", info.name, info.version_sha1)

    assert info.extension
    try:
        info.version = await api.extensionversion.fetch(
            transaction.critic, extension=info.extension, sha1=info.version_sha1
        )
        logger.info("- found existing version: id=%d", info.version.id)
        return
    except api.extensionversion.InvalidSHA1:
        pass

    info.version = (
        await transaction.createExtensionVersion(
            info.extension, info.version_name, info.version_sha1, info.manifest
        )
    ).subject
    logger.info("- created new version: id=%d", info.version.id)


async def ensure_installation(
    transaction: api.transaction.Transaction, info: ExtensionInfo
) -> None:
    logger.info("Resolving extension installation: %s", info.name)

    assert info.extension
    assert info.version

    installation = await api.extensioninstallation.fetch(
        transaction.critic, extension=info.extension
    )

    if installation:
        logger.info("- found existing installation: id=%d", installation.id)

        current_version = await installation.version
        if current_version != info.version:
            logger.info(
                "- updating version: %d -> %d", current_version.id, info.version.id
            )
            modifier = await transaction.modifyExtensionInstallation(installation)
            await modifier.upgradeTo(info.version)
    else:
        installation = (
            await transaction.installExtension(info.extension, info.version)
        ).subject
        logger.info("- created new installation: id=%d", installation)


async def main(critic: api.critic.Critic, arguments: Arguments) -> int:
    extensions_dir = Path(arguments.extensions_dir)
    extensions_json = extensions_dir / "extensions.json"

    try:
        with extensions_json.open() as extensions_json_file:
            extensions_json_data = json.load(extensions_json_file)
    except FileNotFoundError:
        fail(f"{extensions_json}: no such file")

    infos: List[ExtensionInfo] = []
    processed: Set[Path] = set()

    for extension_data in extensions_json_data["extensions"]:
        extension_dir = (extensions_dir / extension_data["name"]).resolve()
        infos.append(await process_extension(arguments, extension_dir))
        processed.add(extensions_dir)

    if arguments.discover:
        for extension_gitdir in extensions_dir.glob("*/.git/"):
            extension_dir = extension_gitdir.parent.resolve()
            if extensions_dir in processed:
                continue
            infos.append(await process_extension(arguments, extension_dir))

    async with api.transaction.start(critic) as transaction:
        for info in infos:
            await ensure_extension(transaction, info)

    async with api.transaction.start(critic) as transaction:
        for info in infos:
            await ensure_version(transaction, info)

    async with api.transaction.start(critic) as transaction:
        for info in infos:
            await ensure_installation(transaction, info)

    return 0
