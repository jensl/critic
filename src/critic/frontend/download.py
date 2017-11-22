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

import aiohttp

from . import NotHandled

from critic import api
from critic.base import mimetype
from critic.wsgi.request import AIOHTTPRequest, MissingParameter, NotFound


async def handle(req: AIOHTTPRequest) -> aiohttp.web.StreamResponse:
    if req.path.strip("/") != "api/download":
        raise NotHandled

    try:
        repository_arg = req.getParameter("repository")
        commit_arg = req.getParameter("commit")
        path = req.getParameter("path")
    except MissingParameter as error:
        raise NotFound(str(error))

    repository_id = None
    try:
        try:
            repository_id = int(repository_arg)
        except ValueError:
            repository = await api.repository.fetch(req.critic, name=repository_arg)
        else:
            repository = await api.repository.fetch(req.critic, repository_id)
    except api.repository.Error as error:
        raise NotFound(str(error))

    commit_id = None
    try:
        try:
            commit_id = int(commit_arg)
        except ValueError:
            commit = await api.commit.fetch(repository, ref=commit_arg)
        else:
            commit = await api.commit.fetch(repository, commit_id)
    except api.commit.Error as error:
        raise NotFound(str(error))

    try:
        contents = await commit.getFileContents(
            await api.file.fetch(req.critic, path=path, create_if_missing=True)
        )
        if contents is None:
            raise NotFound(f"{path}: no such file")
    except api.commit.NotAFile as error:
        raise NotFound(str(error))

    req.setContentType(mimetype.guess_from_filename(path))
    await req.start()
    await req.write(contents)
    return req.response
