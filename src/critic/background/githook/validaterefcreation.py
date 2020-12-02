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

import logging
from typing import Collection, Optional

logger = logging.getLogger(__name__)

from critic import api

from . import ValidateError


async def validate_ref_creation(
    repository: api.repository.Repository,
    ref_name: str,
    *,
    ignore_conflict: Optional[str] = None,
) -> Optional[ValidateError]:
    critic = repository.critic

    async def isref(ref_name: str) -> bool:
        try:
            await repository.resolveRef(ref_name)
        except api.repository.InvalidRef:
            pass
        else:
            return True
        if ref_name.startswith("refs/heads/"):
            # Check the database too.  This is necessary to consider branches
            # that have been archived, but also to detect cases where the Git
            # repository and the database have become out of sync.
            branch_name = ref_name[len("refs/heads/") :]
            async with critic.query(
                """SELECT 1
                     FROM branches
                    WHERE repository={repository_id}
                      AND name={branch_name}
                    LIMIT 1""",
                repository_id=repository.id,
                branch_name=branch_name,
            ) as result:
                if not await result.empty():
                    return True
        return False

    # Check if there's an existing ref whose full path occurs as a parent
    # directory in the created ref's full path.
    components = ref_name.split("/")
    for count in range(3, len(components)):
        existing_ref_name = "/".join(components[:count])
        if existing_ref_name == ignore_conflict:
            continue
        if await isref(existing_ref_name):
            return ValidateError(f"{ref_name}: conflicts with ref: {existing_ref_name}")

    def conflict_error(existing_ref_names: Collection[str]) -> ValidateError:
        existing_ref_name = sorted(existing_ref_names)[0]
        error = "%s: conflicts with ref: %s" % (ref_name, existing_ref_name)
        if len(existing_ref_names) > 1:
            error += " and %d other%s" % (
                len(existing_ref_names) - 1,
                "s" if len(existing_ref_names) != 2 else "",
            )
        return ValidateError(error)

    def not_ignored(names: Collection[str]) -> Collection[str]:
        if ignore_conflict:
            return list(filter(lambda name: name != ignore_conflict, names))
        return names

    # Check if the created ref's full path occurs as a parent directory in the
    # full path of an existing ref.
    existing_ref_names = not_ignored(await repository.listRefs(pattern=ref_name + "/"))
    if existing_ref_names:
        return conflict_error(existing_ref_names)

    # Again, check the database too.  Same reasons as above.
    async with critic.query(
        """SELECT name
             FROM branches
            WHERE repository={repository_id}
              AND name LIKE {pattern}
         ORDER BY name""",
        repository_id=repository.id,
        pattern=ref_name + "/%",
    ) as result:
        existing_ref_names = not_ignored(await result.scalars())
    if existing_ref_names:
        return conflict_error(existing_ref_names)

    return None
