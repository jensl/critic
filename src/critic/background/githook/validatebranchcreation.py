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

from . import ValidateError, Flags, is_review_branch


async def validate_branch_creation(
    repository: api.repository.Repository,
    flags: Flags,
    branch_name: str,
    new_sha1: SHA1,
) -> Optional[ValidateError]:
    # Check if a branch with this name already exists in the database.  If one
    # does, then either the database and the repository are out of sync, or the
    # branch is one that has been archived.
    critic = repository.critic

    try:
        branch = await api.branch.fetch(critic, repository=repository, name=branch_name)
    except api.branch.InvalidName:
        if critic.session_type == "system":
            if is_review_branch(branch_name):
                return ValidateError("would submit new review")
        return None

    if branch.is_archived:
        # This is an archived branch.  Since archived branches are actually
        # deleted from the repository, it's expected that Git thinks we're
        # creating a new branch.
        message = (
            "The branch '%s' in this repository has been archived, "
            "meaning it has been hidden from view to reduce the number "
            "of visible refs in this repository."
        ) % branch_name

        review = await branch.review
        if review:
            url_prefixes = await critic.effective_user.url_prefixes
            message += (
                "\n\n"
                "To continue working on this branch, you need to first "
                "reopen the review that is associated with the branch. "
                " You can do this from the review's front-page:\n\n"
            )
            for url_prefix in url_prefixes:
                message += f"  {url_prefix}/r/{review.id}\n"
        elif new_sha1 == (await branch.head).sha1:
            # Non-review branches can be resurrected by pushing their (supposed)
            # current value.
            return None
        else:
            head = await branch.head
            message += (
                "\n\n"
                "To continue working on this branch, you need to "
                "first resurrect it.  You can do this by first "
                "recreating it with its current value:\n\n"
                "  git push critic %s:refs/heads/%s"
            ) % (head.sha1, branch_name)

        return ValidateError("conflicts with archived branch", message)

    return None
