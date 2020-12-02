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
from critic import dbaccess
from critic import gitaccess
from ..base import TransactionBase
from .modify import ModifyRebase


async def prepare_rebase(
    transaction: TransactionBase,
    review: api.review.Review,
    new_upstream_ref: Optional[str],
    history_rewrite: bool,
    branch: Optional[api.branch.Branch],
) -> ModifyRebase:
    pending = await review.pending_rebase
    if pending is not None:
        creator = await pending.creator
        raise api.review.Error(
            "The review is already being rebased by %s <%s>."
            % (
                creator.fullname,
                creator.email if creator.email is not None else "email missing",
            )
        )

    review_branch = await review.branch
    if not review_branch:
        raise api.review.Error("The review has no branch")

    commitset = await review_branch.commits
    tails = await commitset.filtered_tails

    assert len(commitset.heads) == 1

    old_upstream: Optional[api.commit.Commit] = None
    new_upstream: Optional[api.commit.Commit] = None

    if new_upstream_ref is not None:
        if len(tails) > 1:
            raise api.rebase.Error(
                "Rebase of branch with multiple tails, to new upstream "
                "commit, is not supported."
            )

        old_upstream = next(iter(tails))

        if new_upstream_ref == "0" * 40:
            new_upstream = None
        else:
            if not gitaccess.SHA1_PATTERN.match(new_upstream_ref):
                async with api.critic.Query[str](
                    transaction.critic,
                    """SELECT sha1
                         FROM tags
                        WHERE repository={repository}
                          AND name={new_upstream_ref}""",
                    repository=await review.repository,
                    new_upstream=new_upstream,
                ) as result:
                    try:
                        new_upstream_ref = await result.scalar()
                    except dbaccess.ZeroRowsInResult:
                        raise api.rebase.Error("Specified new_upstream is invalid.")
            try:
                new_upstream = await api.commit.fetch(
                    await review.repository, ref=new_upstream_ref
                )
            except api.repository.InvalidRef:
                raise api.rebase.Error(
                    "The specified new upstream commit does not exist "
                    "in Critic's repository"
                )

    return await ModifyRebase.create(
        transaction, review, old_upstream, new_upstream, branch
    )
