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

import argparse
import hashlib
import io
import logging
import os
from typing import TypedDict, cast
import aiohttp
import tarfile

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from critic import data
from .utils import fail

name = "download-ui"
description = "Download pre-built static UI files."


class Bucket(TypedDict):
    name: str
    region: str


class Archive(TypedDict):
    name: str
    size: int
    sha256: str


class UIJSON(TypedDict):
    cloud: str
    bucket: Bucket
    archive: Archive


async def download_from_amazon_s3(ui_json: UIJSON) -> bytes:
    bucket_name = ui_json["bucket"]["name"]
    region = ui_json["bucket"]["region"]
    archive_name = ui_json["archive"]["name"]

    url = f"https://s3-{region}.amazonaws.com/{bucket_name}/{archive_name}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                fail("Failed to download from cloud storage!")
            return await response.read()


def setup(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(need_session=True)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    ui_json = cast(UIJSON, data.load_json("ui.json"))

    if ui_json.get("cloud") == "Amazon S3":
        archive_bytes = await download_from_amazon_s3(ui_json)
    else:
        fail("Unsupported stored cloud storage details!")

    expected_size = ui_json["archive"]["size"]
    actual_size = len(archive_bytes)
    if actual_size != expected_size:
        fail("Broken download: size mismatch (%d != %d)" % (actual_size, expected_size))

    expected_sha256 = ui_json["archive"]["sha256"]
    actual_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        fail("Broken download: sha256 hash mismatch")

    logger.info("Downloaded %d bytes from %s", actual_size, ui_json["cloud"])

    target_dir = os.path.join(base.configuration()["paths.home"], "ui")

    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)

    archive_file = io.BytesIO(archive_bytes)
    with tarfile.open(mode="r", fileobj=archive_file) as archive:
        for name in archive.getnames():
            if not name.startswith("ui/"):
                logger.debug("Ignoring: %s", name)
                continue
            reader = archive.extractfile(name)
            if reader is None:
                logger.debug("Not a file: %s", name)
                continue
            logger.info("Extracting: %s", name)
            target_path = os.path.join(target_dir, name[len("ui/") :])
            if not os.path.isdir(os.path.dirname(target_path)):
                os.makedirs(os.path.dirname(target_path))
            with open(target_path, "wb") as file:
                file.write(reader.read())

    return 0
