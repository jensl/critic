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
from typing import Optional

logger = logging.getLogger(__name__)

from critic import api
from critic.gitaccess import SHA1

from . import ValidateError, Flags, find_tracked_branch
from .validatebranchcreation import validate_branch_creation
from .validatereviewupdate import validate_review_update


async def validate_branch_update(
    repository: api.repository.Repository,
    flags: Flags,
    branch_name: str,
    old_sha1: SHA1,
    new_sha1: SHA1,
) -> Optional[ValidateError]:
    critic = repository.critic

    # We don't allow manual updates of tracked branches.  However, if |flags|
    # contains a tracked branch id, and it matches the branch being updated,
    # this is the branch tracker pushing, which of course is fine.
    trackedbranch = await find_tracked_branch(repository, branch_name)
    if trackedbranch and trackedbranch.id != flags.get("trackedbranch_id"):
        return ValidateError(
            "tracking branch",
            (
                "The branch %s in this repository tracks %s in %s, and "
                "should not be updated directly in this repository."
            )
            % (branch_name, trackedbranch.source.name, trackedbranch.source.url),
        )

    branch = await api.branch.fetch(critic, repository=repository, name=branch_name)

    if branch is None:
        # Branch missing from the database.  Pretend it is being created.
        return await validate_branch_creation(repository, flags, branch_name, new_sha1)

    review = await branch.review
    if review:
        return await validate_review_update(review, old_sha1, new_sha1)

    return None
