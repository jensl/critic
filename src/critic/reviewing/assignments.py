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
from dataclasses import dataclass
from typing import Collection, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

from .filters import Filters
from critic import api


@dataclass
class Assignment:
    changeset: api.changeset.Changeset
    file: api.file.File
    scope: Optional[api.reviewscope.ReviewScope]
    user: api.user.User

    def __hash__(self) -> int:
        return hash((self.changeset, self.file, self.scope, self.user))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Assignment) and (
            self.changeset,
            self.file,
            self.scope,
            self.user,
        ) == (other.changeset, other.file, other.scope, other.user,)


class PerUser(Set[Assignment]):
    def __init__(self, user: api.user.User):
        self.user = user


class PerFile(Set[Assignment]):
    def __init__(self, file: api.file.File):
        self.file = file


class PerChangeset(Set[Assignment]):
    def __init__(self, changeset: api.changeset.Changeset):
        self.changeset = changeset


class Assignments(Set[Assignment]):
    def __init__(self):
        self.per_changeset: Dict[api.changeset.Changeset, PerChangeset] = {}
        self.per_file: Dict[api.file.File, PerFile] = {}
        self.per_user: Dict[api.user.User, PerUser] = {}

    def __repr__(self) -> str:
        return "Assignments(%r)" % set(self)

    def add_changeset(self, changeset: api.changeset.Changeset) -> PerChangeset:
        if changeset not in self.per_changeset:
            self.per_changeset[changeset] = PerChangeset(changeset)
        return self.per_changeset[changeset]

    def add_file(self, file: api.file.File) -> PerFile:
        if file not in self.per_file:
            self.per_file[file] = PerFile(file)
        return self.per_file[file]

    def add_user(self, user: api.user.User) -> PerUser:
        if user not in self.per_user:
            self.per_user[user] = PerUser(user)
        return self.per_user[user]

    async def add_from(
        self,
        rfc: api.reviewablefilechange.ReviewableFileChange,
        *,
        subject: api.user.User = None
    ) -> None:
        changeset = await rfc.changeset
        file = await rfc.file
        scope = await rfc.scope
        if subject is None:
            for reviewer in await rfc.assigned_reviewers:
                self.add(Assignment(changeset, file, scope, reviewer))
        else:
            self.add(Assignment(changeset, file, scope, subject))


async def initializeFilters(
    review: api.review.Review,
    changesets: Collection[api.changeset.Changeset],
    subject: Optional[api.user.User],
) -> Filters:
    critic = review.critic
    result = Filters()

    files: Set[api.file.File] = set()
    for changeset in changesets:
        filechanges = await changeset.files
        assert filechanges, await changeset.completion_level
        files.update(filechange.file for filechange in filechanges)
    result.setFiles(files)

    filters: List[
        Union[api.repositoryfilter.RepositoryFilter, api.reviewfilter.ReviewFilter]
    ] = []
    for repository_filter in await api.repositoryfilter.fetchAll(
        critic, repository=await review.repository
    ):
        if subject is None or await repository_filter.subject == subject:
            filters.append(repository_filter)
    for review_filter in await api.reviewfilter.fetchAll(critic, review=review):
        if subject is None or await review_filter.subject == subject:
            filters.append(review_filter)
    await result.addFilters(filters)

    return result


async def calculateAssignments(
    review: api.review.Review,
    *,
    changesets: Collection[api.changeset.Changeset] = None,
    subject: api.user.User = None
) -> Assignments:
    """Calculate review assignments for given changesets in a review

       Return value is an Assignments object."""
    critic = review.critic
    assignments = Assignments()

    if changesets is None:
        changeset_per_commit = await review.changesets
        if changeset_per_commit is None:
            return assignments
        changesets = list((await review.changesets).values())

    filters = await initializeFilters(review, changesets, subject)

    for changeset in changesets:
        commit = await changeset.to_commit
        per_changeset = assignments.add_changeset(changeset)
        filechanges = await changeset.files
        assert filechanges

        for filechange in filechanges:
            file = filechange.file
            per_file = assignments.add_file(file)
            data = filters.data[file]

            for user, filterset in data.items():
                per_user = assignments.add_user(user)
                if filterset.filter_type == "watcher":
                    continue
                reviewers: Set[api.user.User] = set()
                default_scope = False
                scopes: Set[api.reviewscope.ReviewScope] = set()
                if await user.isAuthorOf(commit):
                    for filter in filterset:
                        if isinstance(filter, api.repositoryfilter.RepositoryFilter):
                            reviewers.update(await filter.delegates)
                else:
                    reviewers.add(user)
                    for filter in filterset:
                        if filter.default_scope:
                            default_scope = True
                        scopes.update(await filter.scopes)

                def add_assignment(
                    reviewer: api.user.User, scope: api.reviewscope.ReviewScope = None
                ) -> None:
                    assignment = Assignment(changeset, file, scope, reviewer)
                    assignments.add(assignment)
                    per_changeset.add(assignment)
                    per_file.add(assignment)
                    per_user.add(assignment)

                for reviewer in reviewers:
                    if default_scope:
                        add_assignment(reviewer)
                    for scope in scopes:
                        add_assignment(reviewer, scope)

    for rfc in await api.reviewablefilechange.fetchAll(
        review, assignee=subject, is_reviewed=True
    ):
        await assignments.add_from(rfc, subject=subject)

    return assignments


async def currentAssignments(
    review: api.review.Review,
    *,
    changesets: Collection[api.changeset.Changeset] = None,
    subject: api.user.User = None
) -> Assignments:
    assignments = Assignments()

    if changesets is None:
        for rfc in await api.reviewablefilechange.fetchAll(review, assignee=subject):
            await assignments.add_from(rfc, subject=subject)
    else:
        for changeset in changesets:
            for rfc in await api.reviewablefilechange.fetchAll(
                review, changeset=changeset, assignee=subject
            ):
                await assignments.add_from(rfc, subject=subject)

    return assignments
