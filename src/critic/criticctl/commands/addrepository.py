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
import asyncio
import logging
import os
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess

name = "addrepository"
title = "Add repository"


class InvalidSpec(Exception):
    pass


class Spec:
    def __init__(self, spec: str):
        remote, colon, local = spec.partition(":")
        if not colon:
            local = remote
        self.remote = remote.strip()
        self.local = local.strip()
        if not self.remote or not self.local:
            raise InvalidSpec("%s: invalid source branch specification", spec)


async def check_source(arguments: argparse.Namespace) -> Optional[Sequence[Spec]]:
    url = arguments.source
    specs = [Spec(spec) for spec in arguments.branches or []]
    refs = ["HEAD"] + [f"refs/heads/" + spec.remote for spec in specs]

    gitrepository = gitaccess.GitRepository.direct()
    try:
        remote_refs = await gitrepository.lsremote(
            url, *refs, include_symbolic_refs=True
        )
    except gitaccess.GitProcessError:
        logger.error("%s: repository URL invalid or not accessible", url)
        return None

    if specs:
        for spec in specs:
            refname = f"refs/heads/{spec.remote}"
            if refname not in remote_refs.refs:
                logger.error("%s: no such ref in %s", refname, url)
    elif "HEAD" in remote_refs.symbolic_refs:
        head_ref = remote_refs.symbolic_refs["HEAD"]
        if head_ref.startswith("refs/heads/"):
            specs.append(Spec(head_ref[len("refs/heads/") :]))

    if not specs and not arguments.no_branches:
        logger.error(
            "%s: could not determine default branch to mirror (empty repository?)", url
        )
        return None

    return specs


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--name",
        required=True,
        help="Repository short name. Must be unique on the system.",
    )
    parser.add_argument("--path", help="Path relative the repositories directory.")

    source = parser.add_argument_group("Source repository")
    source.add_argument("--source", metavar="URL", help="Git URL of source repository")
    source.add_argument(
        "--branch",
        dest="branches",
        action="append",
        metavar="BRANCH[:LOCAL]",
        help="Mirror branch from the source repository",
    )
    source.add_argument(
        "--no-branches",
        action="store_true",
        help="Do not mirror any branches from the source repository",
    )
    source.add_argument(
        "--tags",
        action="store_const",
        dest="tags",
        const=True,
        help="Mirror all tags from the source repository",
    )
    source.add_argument(
        "--no-tags",
        action="store_const",
        dest="tags",
        const=False,
        help="Do not mirror any tags from the source repository",
    )

    parser.set_defaults(need_session=True, tags=False)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    name: str = arguments.name.strip()
    path: str = arguments.path

    try:
        await api.repository.fetch(critic, name=name)
    except api.repository.InvalidName:
        pass
    else:
        logger.error("%s: a repository with this name already exists", name)
        return 1

    if path is None:
        path = name
    else:
        path = path.strip()

    path = os.path.normpath(path)

    if not path.endswith(".git"):
        path += ".git"

    try:
        await api.repository.fetch(critic, path=path)
    except api.repository.InvalidRepositoryPath:
        pass
    else:
        logger.error("%s: a repository with this path already exists", path)
        return 1

    if arguments.source:
        specs = await check_source(arguments)
        if specs is None:
            return 1
    else:
        specs = None

    async with api.transaction.start(critic) as transaction:
        modifier = await transaction.createRepository(name, path)

        if specs:
            for spec in specs:
                await modifier.trackBranch(arguments.source, spec.remote, spec.local)
            if arguments.tags:
                await modifier.trackTags(arguments.source)

        repository = modifier.subject

    logger.info("Created repository %s [id=%d]", repository.name, repository.id)

    for url in await repository.urls:
        logger.info("Repository URL: %s", url)

    while not await repository.is_ready:
        await asyncio.sleep(0.2)

    logger.info("Repository ready to be used.")

    return 0
