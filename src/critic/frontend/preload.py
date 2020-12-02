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

from dataclasses import dataclass
from typing import Collection, Dict, List, Mapping, Optional
import aiohttp.web
import asyncio
import logging
import urllib.parse

from multidict import MultiDict, MultiDictProxy

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi


@dataclass
class Request:
    method: str
    scheme: str
    path: str

    query: MultiDictProxy[str]

    async def read(self) -> str:
        raise Exception("not supported")


def make_request(path: str, **params: str) -> jsonapi.Request:
    return Request("GET", "internal", path, MultiDictProxy(MultiDict(params.items())))


async def json_responses(
    critic: api.critic.Critic, request: aiohttp.web.BaseRequest
) -> Mapping[str, object]:
    path: str = request.path
    preloaded: Dict[str, object] = {}

    # def get_repository(repository_arg: str) -> api.repository.Repository:
    #     try:
    #         repository_id = int(repository_arg)
    #     except ValueError:
    #         return api.repository.fetch(critic, name=repository_arg)
    #     return api.repository.fetch(critic, repository_id)

    async def preload(
        path: str,
        excludeFields: Optional[Mapping[str, Collection[str]]] = None,
        include: Optional[Collection[str]] = None,
        /,
        **params: str,
    ):
        url = path
        if excludeFields:
            for resource_name, fields in excludeFields.items():
                params[f"fields[{resource_name}]"] = "-" + ",".join(sorted(fields))
        if include:
            params["include"] = ",".join(sorted(include))
        params.setdefault("output_format", "static")
        url += "?" + urllib.parse.urlencode(sorted(item for item in params.items()))
        try:
            result = await jsonapi.handlePreloadRequest(
                critic, make_request(path, **params)
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Crashed while preloading: %s", url)
        else:
            logger.debug("  preloaded: %s", url)
            preloaded[url] = result

    async def preload_changeset(
        path: str,
        *,
        review_id: Optional[int] = None,
        repository: Optional[api.repository.Repository] = None,
    ):
        assert path.startswith("changeset/")

        if review_id is None:
            review = None
        else:
            review = await api.review.fetch(critic, review_id)
            repository = await review.repository
        assert repository is not None

        path = path[len("changeset/") :]
        changeset_id = None
        excludeFields: Dict[str, List[str]] = {"comments": ["location"]}

        url = "api/v1/changesets"
        params: Dict[str, str] = {}

        component, _, rest = path.partition("/")
        if component == "by-sha1":
            refs, _, rest = rest.partition("/")
            first, _, second = refs.partition("..")
            if not second:
                params["commit"] = first
            else:
                if first:
                    params["from"] = first
                params["to"] = second
        elif component == "automatic":
            automatic, _, rest = rest.partition("/")
            params["automatic"] = automatic
        else:
            changeset_id = int(component)
            url += f"/{changeset_id}"
        include = {"commits", "filechanges", "files"}
        if review:
            include.update(
                {"changesets", "comments", "replies", "reviewablefilechanges", "users"}
            )
            params["review"] = str(review.id)
        else:
            params["repository"] = str(repository.id)
        await preload(url, excludeFields, include, **params)

    logger.debug("preload for: %r", request.path)

    await preload("api/v1/sessions/current", None, ("users",))
    await preload("api/v1/users")
    await preload("api/v1/usersettings", scope="ui")
    await preload(
        "api/v1/extensioninstallations", None, ("extensions", "extensionversions")
    )

    if path.startswith("/review/"):
        components = path.strip("/").split("/")
        if len(components) < 2:
            return preloaded
        try:
            review_id = int(components[1])
        except ValueError:
            return preloaded

        include = {
            "batches",
            "branches",
            "changesets:limit=20",
            "comments",
            "commits",
            "files",
            "rebases",
            "replies",
            "repositories",
            "reviewablefilechanges:limit=100",
            "reviewfilters",
            "reviewtags",
            "users",
        }
        excludeFields = {
            "changesets": [
                "completion_level",
                "contributing_commits",
                "review_state.comments",
            ],
            "comments": ["location"],
        }
        await preload(
            "api/v1/reviews/%d" % review_id,
            excludeFields,
            include,
        )

        if critic.actual_user:
            await preload(
                "api/v1/batches",
                None,
                ("reviews",),
                review=str(review_id),
                unpublished="yes",
            )

        if len(components) >= 3:
            if components[2] == "changes":
                await preload_changeset(
                    "changeset/automatic/everything", review_id=review_id
                )
            elif components[2] == "changeset":
                await preload_changeset("/".join(components[2:]), review_id=review_id)
    elif path.startswith("/repository/"):
        repository_arg, _, rest = path[len("/repository/") :].partition("/")
        try:
            repository_id = int(repository_arg)
        except ValueError:
            repository = await api.repository.fetch(critic, name=repository_arg)
            await preload(
                "api/v1/repositories", None, ("commits",), name=repository_arg
            )
        else:
            repository = await api.repository.fetch(critic, repository_id)
            await preload("api/v1/repositories/{repository_id}", None, ("commits",))

        if rest and rest.startswith("changeset"):
            await preload_changeset(rest, repository=repository)
    # elif not path:
    #     await preload("api/v1/reviewsummaries", offset=0, count=10, type="all")
    #     if not critic.effective_user.is_anonymous:
    #         await preload(
    #             "api/v1/reviewsummaries", offset=0, count=10, type="own")
    #         await preload(
    #             "api/v1/reviewsummaries", offset=0, count=10, type="other")

    return preloaded
