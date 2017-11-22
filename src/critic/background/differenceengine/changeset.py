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
from typing import Collection, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic.gitaccess import SHA1

from . import deserialize_key
from .changedfile import ChangedFile
from .changedlines import ChangedLines
from .jobgroup import JobGroup


class Changeset(JobGroup["Changeset"]):
    def __init__(
        self,
        runner: jobrunner.JobRunner,
        changeset_id: int,
        repository_id: int,
        conflicts: bool,
    ):
        super().__init__(runner, key=(changeset_id,))
        self.changeset_id = changeset_id
        self.repository_id = repository_id
        self.conflicts = conflicts
        self.language_ids = runner.language_ids
        self.syntax_highlight = False

    def __str__(self) -> str:
        return "changeset %d" % self.changeset_id

    def start(self) -> None:
        self.runner.service.monitor_changeset(self.changeset_id)

    async def calculate_remaining(
        self, critic: api.critic.Critic, initial_calculation: bool = False
    ) -> None:
        from .analyzechangedlines import AnalyzeChangedLines
        from .calculatefiledifference import CalculateFileDifference
        from .calculatestructuredifference import CalculateStructureDifference
        from .detectfilelanguages import DetectFileLanguages
        from .examinefiles import ExamineFiles
        from .syntaxhighlightfile import SyntaxHighlightFile

        if initial_calculation:
            async with api.critic.Query[str](
                critic,
                """SELECT repositories.path
                        FROM repositories
                        JOIN changesets ON (changesets.repository=repositories.id)
                    WHERE changesets.id={changeset_id}""",
                changeset_id=self.changeset_id,
            ) as repository_path:
                self.repository_path = await repository_path.scalar()

        async with api.critic.Query[str](
            critic,
            """SELECT job_key
                 FROM changeseterrors
                WHERE changeset={changeset_id}""",
            changeset_id=self.changeset_id,
        ) as failed_jobs:
            self.failed.update(map(deserialize_key, await failed_jobs.scalars()))

        async with api.critic.Query[Tuple[bool, bool, int, SHA1, int, SHA1, int, bool]](
            critic,
            """SELECT changesets.processed, changesets.complete,
                        to_commit, to_commits.sha1,
                        from_commit, from_commits.sha1,
                        for_merge, cscd.changeset IS NOT NULL
                    FROM changesets
                    JOIN commits AS to_commits ON (to_commits.id=to_commit)
        LEFT OUTER JOIN commits AS from_commits ON (from_commits.id=from_commit)
        LEFT OUTER JOIN changesetcontentdifferences AS cscd ON (
                        cscd.changeset=changesets.id
                        )
                WHERE changesets.id={changeset_id}""",
            changeset_id=self.changeset_id,
        ) as pending_changesets:
            (
                structure_difference_processed,
                structure_difference_complete,
                to_commit_id,
                to_commit_sha1,
                from_commit_id,
                from_commit_sha1,
                for_merge_id,
                content_difference_requested,
            ) = await pending_changesets.one()

        if for_merge_id is not None:
            # For merge differences, we want to filter the set of changed files
            # before we start calculating the content difference, so pretend it
            # hasn't been requested for now.
            #
            # This only affects whether the CalculateStructureDifference job
            # produces ExamineFiles jobs as immediate follow-ups, which is an
            # optimization.
            content_difference_requested = False

        if for_merge_id == to_commit_id:
            async with api.critic.Query[Tuple[int, bool, SHA1]](
                critic,
                """SELECT changesets.id, processed, sha1
                     FROM changesets
                     JOIN commits ON (commits.id=from_commit)
                    WHERE to_commit={to_commit_id}
                      AND for_merge={for_merge_id}""",
                to_commit_id=from_commit_id,
                for_merge_id=for_merge_id,
            ) as reference:
                (
                    reference_id,
                    reference_processed,
                    merge_base_sha1,
                ) = await reference.one()

            if not reference_processed:
                self.add_job(
                    CalculateStructureDifference(
                        self,
                        reference_id,
                        merge_base_sha1,
                        from_commit_sha1,
                        False,
                        True,
                    )
                )
        else:
            reference_processed = True

        if not structure_difference_processed:
            self.add_job(
                CalculateStructureDifference(
                    self,
                    self.changeset_id,
                    from_commit_sha1,
                    to_commit_sha1,
                    content_difference_requested,
                    for_merge_id is not None,
                )
            )

        async with api.critic.Query[Tuple[bool, bool]](
            critic,
            """SELECT evaluated, requested
                 FROM changesethighlightrequests
                WHERE changeset={changeset_id}""",
            changeset_id=self.changeset_id,
        ) as syntax_highlight_request:
            (
                syntax_highlight_evaluated_before,
                syntax_highlight_requested,
            ) = await syntax_highlight_request.one()

        self.syntax_highlight = syntax_highlight_requested

        if not reference_processed or not structure_difference_processed:
            # Calculate structure difference, and do nothing else.  Many of the
            # other calculations in this function depend on the structure
            # difference to determine what else needs to be done, and will think
            # the rest is all done if the structure difference is "empty."
            return

        async with critic.transaction() as cursor:
            if for_merge_id == to_commit_id:
                # Prune files from both the primary changeset and the reference
                # changeset that weren't modified by both.  We don't need to
                # calculate content differences for any such files, since there
                # can be no overlapping changes in them.
                await cursor.executemany(
                    """DELETE FROM changesetfiles
                        WHERE changeset={prune_id}
                          AND file NOT IN (SELECT file
                                             FROM changesetfiles
                                            WHERE changeset={other_id})""",
                    [
                        {"prune_id": self.changeset_id, "other_id": reference_id},
                        {"prune_id": reference_id, "other_id": self.changeset_id},
                    ],
                )

                # Mark the reference changeset as complete.
                await cursor.execute(
                    """UPDATE changesets
                          SET complete=TRUE
                        WHERE id={changeset_id}""",
                    changeset_id=reference_id,
                )
                # The reference changeset should now be picked up for content
                # difference processing.
                self.runner.find_new_incomplete = True

            # Mark the (primary) changeset as complete.
            await cursor.execute(
                """UPDATE changesets
                      SET complete=TRUE
                    WHERE id={changeset_id}""",
                changeset_id=self.changeset_id,
            )

            # Publish a message to notify interested parties about the updated
            # completion level.
            self.service.update_changeset(self.changeset_id)

        if not syntax_highlight_requested:
            syntax_highlight_complete_before = True
        elif syntax_highlight_evaluated_before:
            async with api.critic.Query[bool](
                critic,
                """SELECT TRUE
                     FROM highlightfiles AS hlf
                     JOIN changesetfiledifferences AS csfd ON (
                            csfd.old_highlightfile=hlf.id OR
                            csfd.new_highlightfile=hlf.id
                          )
                    WHERE NOT hlf.highlighted
                      AND csfd.changeset={changeset_id}
                    LIMIT 1""",
                changeset_id=self.changeset_id,
            ) as syntax_highlight_complete:
                syntax_highlight_complete_before = (
                    await syntax_highlight_complete.empty()
                )
        else:
            syntax_highlight_complete_before = False

        logger.debug("syntax_highlight_requested=%r", syntax_highlight_requested)
        logger.debug(
            "syntax_highlight_evaluated_before=%r", syntax_highlight_evaluated_before
        )
        logger.debug(
            "syntax_highlight_complete_before=%r", syntax_highlight_complete_before
        )

        async with api.critic.Query[bool](
            critic,
            """SELECT complete
                 FROM changesetcontentdifferences
                WHERE changeset={changeset_id}""",
            changeset_id=self.changeset_id,
        ) as content_difference:
            content_difference_complete_before = await content_difference.scalar()

        if initial_calculation:
            # No Changeset group should have been created if all work is done
            # already.
            assert not (
                content_difference_complete_before and syntax_highlight_complete_before
            )

        content_difference_jobs: Set[job.Job[Changeset]] = set()

        ChangedFilesRow = Tuple[int, str, SHA1, int, SHA1, int]

        # Search for any row in |changesetfiles| not matched by a row in
        # |changesetfiledifferences|.
        async with api.critic.Query[ChangedFilesRow](
            critic,
            """SELECT csf.file, files.path, csf.old_sha1, csf.old_mode,
                      csf.new_sha1, csf.new_mode
                 FROM changesetfiles AS csf
                 JOIN files ON (files.id=csf.file)
      LEFT OUTER JOIN changesetfiledifferences AS csfd ON (
                        csfd.changeset=csf.changeset AND
                        csfd.file=csf.file
                      )
                WHERE csf.changeset={changeset_id}
                  AND csfd.changeset IS NULL""",
            changeset_id=self.changeset_id,
        ) as changed_files_result:
            changed_files = [ChangedFile(*row) async for row in changed_files_result]

        if changed_files:
            content_difference_jobs.update(
                ExamineFiles.for_files(
                    self, from_commit_sha1, to_commit_sha1, changed_files
                )
            )
            all_files_examined = False
        else:
            all_files_examined = True

        # Search for any row in |changesetfiledifferences| whose
        # |comparison_pending| is true.
        async with api.critic.Query[ChangedFilesRow](
            critic,
            """SELECT csf.file, files.path, csf.old_sha1, csf.old_mode,
                      csf.new_sha1, csf.new_mode
                 FROM changesetfiles AS csf
                 JOIN changesetfiledifferences AS csfd USING (changeset, file)
                 JOIN files ON (files.id=csf.file)
                WHERE csf.changeset={changeset_id}
                  AND csfd.comparison_pending""",
            changeset_id=self.changeset_id,
        ) as changed_files_result:
            changed_files = [ChangedFile(*row) async for row in changed_files_result]

        content_difference_jobs.update(
            CalculateFileDifference.for_files(
                self, from_commit_sha1, to_commit_sha1, changed_files
            )
        )

        # Search for any files with unanalyzed blocks of changed lines.
        per_file: Dict[int, Tuple[ChangedFile, List[ChangedLines]]] = {}
        async with api.critic.Query[ChangedFilesRow](
            critic,
            """SELECT DISTINCT file, path, old_sha1, old_mode,
                               new_sha1, new_mode
                 FROM changesetchangedlines
                 JOIN changesetfiles USING (changeset, file)
                 JOIN files ON (files.id=file)
                WHERE changeset={changeset_id}
                  AND analysis IS NULL""",
            changeset_id=self.changeset_id,
        ) as changed_files_result:
            async for file_id, path, old_sha1, old_mode, new_sha1, new_mode in changed_files_result:
                per_file[file_id] = (
                    ChangedFile(file_id, path, old_sha1, old_mode, new_sha1, new_mode),
                    [],
                )

        # For each such file, fetch all blocks. We need all blocks to get
        # absolute per-block offsets, which is necessary to process each block
        # in isolation.
        async with api.critic.Query[Tuple[int, int, int, int, int, int, int, bool]](
            critic,
            """SELECT file, "index", "offset", delete_count, delete_length,
                      insert_count, insert_length, analysis IS NULL
                 FROM changesetchangedlines
                WHERE changeset={changeset_id}
                  AND {file=file_ids:array}
             ORDER BY file, "index" """,
            changeset_id=self.changeset_id,
            file_ids=list(per_file.keys()),
        ) as changed_lines_result:
            previous_file_id = None
            async for (
                file_id,
                index,
                offset,
                delete_count,
                delete_length,
                insert_count,
                insert_length,
                needs_analysis,
            ) in changed_lines_result:
                if file_id != previous_file_id:
                    delete_offset = insert_offset = 0
                    previous_file_id = file_id
                _, blocks = per_file[file_id]
                delete_offset += offset
                insert_offset += offset
                if needs_analysis:
                    blocks.append(
                        ChangedLines(
                            index,
                            offset,
                            delete_offset,
                            delete_count,
                            delete_length,
                            insert_offset,
                            insert_count,
                            insert_length,
                        )
                    )
                delete_offset += delete_length
                insert_offset += insert_length
        for changed_file, blocks in per_file.values():
            content_difference_jobs.update(
                AnalyzeChangedLines.for_blocks(self, changed_file, blocks)
            )

        # Remove any previous failed jobs.  We shouldn't try them again.
        #
        # Note: This may lead to us setting |complete| to true below.  This is
        # intentional to stop us from looking at this changeset any more.
        content_difference_jobs -= self.failed

        if content_difference_jobs:
            self.add_jobs(content_difference_jobs)
        elif not content_difference_complete_before:
            # Nothing to do, so the content difference must be completely
            # processed.
            async with critic.transaction() as cursor:
                logger.debug("runner thread: changeset %d complete" % self.changeset_id)
                await cursor.execute(
                    """UPDATE changesetcontentdifferences
                          SET complete=TRUE
                        WHERE changeset={changeset_id}""",
                    changeset_id=self.changeset_id,
                )

            # Publish a message to notify interested parties about the updated
            # completion level.
            self.runner.service.update_changeset(self.changeset_id)

        # Search for any files that need to be syntax highlighted.
        if all_files_examined and not syntax_highlight_complete_before:
            async with api.critic.Query[
                Tuple[int, str, SHA1, int, int, SHA1, int, int]
            ](
                critic,
                """SELECT file, path, old_sha1, old_mode, old_length, new_sha1,
                          new_mode, new_length
                     FROM changesetfiles
                     JOIN changesetfiledifferences USING (changeset, file)
                     JOIN files ON (files.id=file)
                    WHERE changesetfiles.changeset={changeset_id}""",
                changeset_id=self.changeset_id,
            ) as changed_files_with_lengths:
                changed_files = [
                    ChangedFile(
                        file_id, path, old_sha1, old_mode, new_sha1, new_mode
                    ).set_status((old_lines, new_lines))
                    async for (
                        file_id,
                        path,
                        old_sha1,
                        old_mode,
                        old_lines,
                        new_sha1,
                        new_mode,
                        new_lines,
                    ) in changed_files_with_lengths
                ]

            logger.debug("changed_files=%r", changed_files)

            syntax_highlight_jobs: Set[job.Job[Changeset]] = set()
            detect_file_language_jobs: Set[job.Job[Changeset]] = set()

            async with api.critic.Query[Tuple[int, SHA1, bool, bool, str]](
                critic,
                """SELECT DISTINCT csfd.file, hlf.sha1, hlf.conflicts,
                                   hlf.highlighted, hll.label
                     FROM highlightfiles AS hlf
                     JOIN highlightlanguages AS hll ON (hll.id=hlf.language)
                     JOIN changesetfiledifferences AS csfd ON (
                            csfd.old_highlightfile=hlf.id OR
                            csfd.new_highlightfile=hlf.id
                          )
                    WHERE csfd.changeset={changeset_id}""",
                changeset_id=self.changeset_id,
            ) as highlight_files:
                highlight_files_rows = await highlight_files.all()
            evaluated_files = set(
                (file_id, sha1) for (file_id, sha1, _, _, _) in highlight_files_rows
            )
            syntax_highlight_jobs.update(
                SyntaxHighlightFile(self, sha1, language_label, conflicts)
                for _, sha1, conflicts, is_highlighted, language_label in highlight_files_rows
                if not is_highlighted
            )

            logger.debug("evaluated_files=%r", evaluated_files)
            logger.debug("syntax_highlight_jobs=%r", syntax_highlight_jobs)

            # cursor.execute("""SELECT file, sha1
            #                     FROM highlightfiles
            #                    WHERE context=%s
            #                      AND language IS NULL""",
            #                (self.highlight_context_id,))
            # evaluated_files.update(cursor)

            # Remove any previous failed jobs.  We shouldn't try them again.
            #
            # Note: This may lead to us setting |complete| to true below.  This
            # is intentional to stop us from looking at this changeset any more.
            syntax_highlight_jobs -= self.failed

            if syntax_highlight_jobs:
                self.add_jobs(syntax_highlight_jobs)

            if not syntax_highlight_evaluated_before:
                detect_file_language_jobs.update(
                    DetectFileLanguages.for_files(
                        self,
                        changed_files,
                        skip_file_versions=evaluated_files,
                        process_all=True,
                    )
                )

                # Remove any previous failed jobs.  We shouldn't try them again.
                #
                # Note: This may lead to us setting |evaluated| to true below.
                # This is intentional to stop us from looking at this changeset
                # any more.
                detect_file_language_jobs -= self.failed

                logger.debug("detect_file_language_jobs=%r", detect_file_language_jobs)

                self.add_jobs(detect_file_language_jobs)

            evaluated = all_files_examined and not detect_file_language_jobs
            complete = all_files_examined and not syntax_highlight_jobs

            if (evaluated and not syntax_highlight_evaluated_before) or complete:
                if evaluated and not syntax_highlight_evaluated_before:
                    logger.debug(
                        "runner thread: highlighting of changeset %d evaluated"
                        % self.changeset_id
                    )
                    async with critic.transaction() as cursor:
                        await cursor.execute(
                            """UPDATE changesethighlightrequests
                                  SET evaluated={evaluated}
                                WHERE changeset={changeset_id}""",
                            evaluated=evaluated,
                            changeset_id=self.changeset_id,
                        )
                if complete:
                    logger.debug(
                        "runner thread: highlighting of changeset %d complete"
                        % self.changeset_id
                    )

                    # Publish a message to notify interested parties about the
                    # updated completion level.
                    self.runner.service.update_changeset(self.changeset_id)

    def jobs_finished(self, jobs: Collection[job.Job[Changeset]]) -> None:
        # Publish a message to notify interested parties about the
        # updated completion level.
        logger.debug("%d: %d jobs_finished", self.changeset_id, len(jobs))
        self.runner.service.update_changeset(self.changeset_id)

    def group_finished(self) -> None:
        logger.debug("%d: finished", self.changeset_id)
        self.runner.service.forget_changeset(self.changeset_id)

    @staticmethod
    async def find_incomplete(
        critic: api.critic.Critic, runner: jobrunner.JobRunner
    ) -> Collection[Changeset]:
        # First, find all changesets with an incomplete structure difference,
        # skipping the reference changeset for merges.
        async with critic.query(
            """SELECT changesets.id, repository, is_replay
                 FROM changesets
                WHERE NOT complete
                  AND (for_merge IS NULL OR for_merge=to_commit)"""
        ) as result:
            changesets = set(await result.all())

        # Second, find all changesets with an incomplete content difference.
        async with critic.query(
            """SELECT changesets.id, repository, is_replay
                 FROM changesets
                 JOIN changesetcontentdifferences AS cscd ON (
                        cscd.changeset=changesets.id
                      )
                WHERE changesets.complete
                  AND NOT cscd.complete"""
        ) as result:
            changesets.update(await result.all())

        # Third, find all changesets that haven't been completely syntax
        # highlighted.
        async with critic.query(
            """SELECT changesets.id, repository, is_replay
                 FROM changesets
                 JOIN changesethighlightrequests AS cshlr ON (
                        cshlr.changeset=changesets.id
                      )
                WHERE changesets.complete
                  AND cshlr.requested
                  AND NOT cshlr.evaluated"""
        ) as result:
            changesets.update(await result.all())
        async with critic.query(
            """SELECT DISTINCT changesets.id, changesets.repository,
                               is_replay
                 FROM changesets
                 JOIN changesethighlightrequests AS cshlr ON (
                        cshlr.changeset=changesets.id
                      )
                 JOIN changesetfiledifferences AS csfd ON (
                        csfd.changeset=changesets.id
                      )
                 JOIN highlightfiles AS hlf ON (
                        hlf.id=csfd.old_highlightfile OR
                        hlf.id=csfd.new_highlightfile
                      )
                WHERE changesets.complete
                  AND cshlr.requested
                  AND NOT hlf.highlighted"""
        ) as result:
            changesets.update(await result.all())

        return set(
            Changeset(runner, changeset_id, repository_id, conflicts)
            for changeset_id, repository_id, conflicts in changesets
        )


from . import job, jobrunner
