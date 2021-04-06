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

# type: ignore

import logging

logger = logging.getLogger(__name__)

from critic import api


async def render_commit(group, commit, context_lines):
    cache = group.cache.setdefault("render_commit", {})
    cached = cache.get((commit, context_lines))

    if cached is not None:
        logger.debug("Using cached commit rendering")
        return cached

    critic = commit.critic
    changeset = await api.changeset.fetch(critic, single_commit=commit)

    await changeset.ensure_completion_level("analysis")

    filediffs = {
        filediff.filechange: filediff
        for filediff in await api.filediff.fetchAll(changeset)
    }

    deletions = insertions = 0

    def reconstruct_line_old(line):
        return "".join(part.content for part in line.content if part.state <= 0)

    def reconstruct_line_new(line):
        return "".join(part.content for part in line.content if part.state >= 0)

    filechanges = await changeset.files
    diff_lines = []

    for filechange in filechanges:
        path = filechange.file.path

        diff_lines.extend(
            [
                "--- a/" + ("dev/null" if filechange.was_added else path),
                "+++ b/" + ("dev/null" if filechange.was_deleted else path),
            ]
        )

        filediff = filediffs.get(filechange)
        if filediff:
            for chunk in await filediff.getMacroChunks(context_lines):
                chunk_lines = []
                deleted_lines = []
                deleted_count = 0
                inserted_lines = []
                inserted_count = 0

                for line in chunk.lines:
                    if line.type not in (line.INSERTED, line.CONTEXT):
                        deleted_lines.append("-" + reconstruct_line_old(line))
                        deleted_count += 1
                    if line.type not in (line.DELETED, line.CONTEXT):
                        inserted_lines.append("+" + reconstruct_line_new(line))
                        inserted_count += 1
                    if line.type == line.CONTEXT:
                        if deleted_lines:
                            chunk_lines.extend(deleted_lines)
                            deleted_lines = []
                        if inserted_lines:
                            chunk_lines.extend(inserted_lines)
                            inserted_lines = []
                        chunk_lines.append(" " + reconstruct_line_new(line))

                diff_lines.append(
                    "@@ -%d,%d +%d,%d @@"
                    % (
                        chunk.old_offset + 1,
                        chunk.old_count,
                        chunk.new_offset + 1,
                        chunk.new_count,
                    )
                )
                diff_lines.extend(chunk_lines)
                diff_lines.extend(deleted_lines)
                diff_lines.extend(inserted_lines)

                deletions += deleted_count
                insertions += inserted_count
        else:
            diff_lines.append("  Binary file.")

    author = commit.author
    timestamp = author.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    commit_lines = [
        f"Commit: {commit.sha1}",
        f"Author: {author.name} <{author.email}> at {timestamp}",
        "",
    ]

    def plural_s(count):
        return "s" if count != 1 else ""

    changed_files = len(filechanges)
    shortstats = [f" {changed_files} file{plural_s(changed_files)} changed"]

    if insertions:
        shortstats.append(f"{insertions} insertion{plural_s(insertions)}(+)")
    if deletions:
        shortstats.append(f"{deletions} deletion{plural_s(deletions)}(-)")

    commit_lines.extend(commit.message.splitlines())
    commit_lines.extend(["", ", ".join(shortstats), ""])
    commit_lines.extend(diff_lines)

    cache[(commit, context_lines)] = commit_lines

    return commit_lines
