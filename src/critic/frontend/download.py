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

import aiohttp.web

from . import NotHandled

from critic import api
from critic.base import mimetype


async def handle(
    critic: api.critic.Critic, req: aiohttp.web.BaseRequest
) -> aiohttp.web.StreamResponse:
    if req.path.strip("/") != "api/download":
        raise NotHandled

    try:
        repository_arg = req.query["repository"]
        commit_arg = req.query["commit"]
        path = req.query["path"]
    except KeyError as error:
        raise aiohttp.web.HTTPBadRequest(text=str(error))

    repository_id = None
    try:
        try:
            repository_id = int(repository_arg)
        except ValueError:
            repository = await api.repository.fetch(critic, name=repository_arg)
        else:
            repository = await api.repository.fetch(critic, repository_id)
    except api.repository.Error as error:
        raise aiohttp.web.HTTPNotFound(text=str(error))

    commit_id = None
    try:
        try:
            commit_id = int(commit_arg)
        except ValueError:
            commit = await api.commit.fetch(repository, ref=commit_arg)
        else:
            commit = await api.commit.fetch(repository, commit_id)
    except api.commit.Error as error:
        raise aiohttp.web.HTTPNotFound(text=str(error))

    try:
        contents = await commit.getFileContents(
            await api.file.fetch(critic, path=path, create_if_missing=True)
        )
        if contents is None:
            raise aiohttp.web.HTTPNotFound(text=f"{path}: no such file")
    except api.commit.NotAFile as error:
        raise aiohttp.web.HTTPNotFound(text=str(error))

    response = aiohttp.web.StreamResponse(
        headers={"content-type": mimetype.guess_from_filename(path)}
    )

    await response.prepare(req)
    await response.write(contents)

    return response
