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

import logging
from typing import Dict, Iterable, Set, Tuple

logger = logging.getLogger(__name__)

from critic import api


class FileIds:
    __file_ids: Dict[str, int]
    __update_needed: Set[str]

    def __init__(self) -> None:
        # Cached path=>id mappings.  Since files are only ever insert into the
        # database and never removed, this cache is automatically correct for
        # all files that it has ever found in the database.
        self.__file_ids = {}
        # Contains paths that probably exist, but that we don't have in
        # |__file_ids| yet.
        self.__update_needed = set()

    def __getitem__(self, path: str) -> int:
        return self.__file_ids[path]

    async def ensure_paths(
        self, critic: api.critic.Critic, paths: Iterable[str]
    ) -> None:
        missing_paths = set(paths).difference(self.__file_ids)
        if not missing_paths:
            return
        logger.debug("file id cache: inserting %d paths" % len(missing_paths))
        files = await api.file.fetchMany(critic, paths=paths, create_if_missing=True)
        self.__file_ids.update((file.path, file.id) for file in files)

    async def update(self, critic: api.critic.Critic) -> None:
        async with api.critic.Query[Tuple[str, int]](
            critic, "SELECT path, id FROM files"
        ) as result:
            self.__file_ids.update(await result.all())
        logger.debug("file id cache: loaded %d paths" % len(self.__file_ids))
