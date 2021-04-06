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
import time
from collections import OrderedDict
from typing import Dict, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

from critic import api, dbaccess
from critic import gitaccess
from critic.gitaccess import SHA1

# Number of probably new SHA1s to lookup in the |commits| table per query. The
# possible total number of potentially new SHA1s to process is essentially
# unbounded, so some chunking is most likely a good idea.
SHA1_LOOKUP_CHUNK_SIZE = 100


async def insert_commits(
    repository: api.repository.Repository, sha1: SHA1
) -> Sequence[gitaccess.GitCommit]:
    before = time.time()

    critic = repository.critic
    repository_id = repository.id
    low_level = repository.low_level
    decode = await repository.getDecode(sha1)

    sha1 = await low_level.revparse(sha1, object_type="commit")

    logger.debug("inserting: %s", sha1)

    async with critic.query("SELECT 1 FROM commits LIMIT 1") as result:
        emptydb = await result.empty()

    async with critic.query(
        """SELECT DISTINCT sha1
             FROM (
               SELECT sha1
                 FROM commits
                 JOIN branches ON (branches.head=commits.id)
                WHERE branches.repository={repository_id}
             ORDER BY commits.commit_time DESC
                  ) AS branchheads
            LIMIT 50""",
        repository_id=repository_id,
    ) as result:
        exclude = set(await result.scalars())

    try:
        head_sha1 = await low_level.revparse("HEAD", object_type="commit")
    except gitaccess.GitReferenceError:
        pass
    else:
        if head_sha1 != sha1:
            exclude.add(head_sha1)

    commits: Dict[SHA1, gitaccess.GitCommit] = OrderedDict()

    async for commit_id, gitobject in low_level.fetch(include=[sha1], exclude=exclude):
        if isinstance(gitobject, Exception):
            raise gitobject
        commits[commit_id] = gitobject.asCommit()

    sha1s = list(commits.keys())
    new_sha1s = set(sha1s)

    if not emptydb:
        for offset in range(0, len(new_sha1s), SHA1_LOOKUP_CHUNK_SIZE):
            sha1s_chunk = sha1s[offset : offset + SHA1_LOOKUP_CHUNK_SIZE]
            async with critic.query(
                """SELECT sha1
                     FROM commits
                    WHERE sha1=ANY({sha1s})""",
                sha1s=sha1s_chunk,
            ) as result:
                new_sha1s.difference_update(await result.scalars())

    gitusers: Set[Tuple[str, str]] = set()
    gituser_names: Set[str] = set()
    gituser_emails: Set[str] = set()
    new_commits = []
    edges_values: Set[Tuple[SHA1, SHA1]] = set()

    for sha1, commit in commits.items():
        if sha1 in new_sha1s:
            author_name = decode.commitMetadata(commit.author.name)
            author_email = decode.commitMetadata(commit.author.email)
            committer_name = decode.commitMetadata(commit.committer.name)
            committer_email = decode.commitMetadata(commit.committer.email)

            gitusers.update(
                [
                    (author_name, author_email),
                    (committer_name, committer_email),
                ]
            )
            gituser_names.update([author_name, committer_name])
            gituser_emails.update([author_email, committer_email])

            new_commits.append(commit)
            edges_values.update(
                (parent_sha1, commit.sha1) for parent_sha1 in commit.parents
            )

    middle = time.time()

    async with critic.transaction() as cursor:
        async with cursor.query(
            """SELECT id, fullname, email
                 FROM gitusers
                WHERE fullname=ANY({gituser_names})
                   OR email=ANY({gituser_emails})""",
            gituser_names=list(gituser_names),
            gituser_emails=list(gituser_emails),
        ) as result:
            gituser_ids = {
                (fullname, email): gituser_id
                async for gituser_id, fullname, email in result
            }

        new_gitusers = gitusers.difference(gituser_ids.keys())
        if new_gitusers:
            logger.debug("New git users: %r", new_gitusers)

            await cursor.executemany(
                """INSERT
                     INTO gitusers (fullname, email)
                   VALUES ({name}, {email})""",
                ({"name": name, "email": email} for name, email in new_gitusers),
            )

            new_gituser_names = set(name for name, _ in new_gitusers)
            new_gituser_emails = set(email for _, email in new_gitusers)

            async with cursor.query(
                """SELECT id, fullname, email
                     FROM gitusers
                    WHERE fullname=ANY({gituser_names})
                       OR email=ANY({gituser_emails})""",
                gituser_names=list(new_gituser_names),
                gituser_emails=list(new_gituser_emails),
            ) as result:
                gituser_ids.update(
                    {
                        (fullname, email): gituser_id
                        async for gituser_id, fullname, email in result
                    }
                )

        await cursor.executemany(
            """INSERT INTO commits (sha1, author_gituser, author_time,
                                    commit_gituser, commit_time)
               VALUES ({sha1}, {author_gituser}, {author_time},
                       {commit_gituser}, {commit_time})""",
            (
                dbaccess.parameters(
                    sha1=commit.sha1,
                    author_gituser=gituser_ids[
                        (
                            decode.commitMetadata(commit.author.name),
                            decode.commitMetadata(commit.author.email),
                        )
                    ],
                    author_time=commit.author.time,
                    commit_gituser=gituser_ids[
                        (
                            decode.commitMetadata(commit.committer.name),
                            decode.commitMetadata(commit.committer.email),
                        )
                    ],
                    commit_time=commit.committer.time,
                )
                for commit in new_commits
            ),
        )

        await cursor.executemany(
            """INSERT INTO edges (parent, child)
                    SELECT parents.id, children.id
                      FROM commits AS parents,
                           commits AS children
                     WHERE parents.sha1={parent_sha1}
                       AND children.sha1={child_sha1}""",
            (
                {"parent_sha1": parent_sha1, "child_sha1": child_sha1}
                for parent_sha1, child_sha1 in edges_values
            ),
        )

    after = time.time()
    duration = after - before

    if duration > 0.01:
        logger.info(
            "Inserted %d commits in %.2f (%.2f) seconds",
            len(new_commits),
            middle - before,
            duration,
        )

    return list(commits.values())
