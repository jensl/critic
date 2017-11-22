# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

logger = logging.getLogger(__name__)

from critic import api


class Location:
    def __init__(self, file, sha1, first_line, last_line, is_new=True):
        self.file = file
        self.sha1 = sha1
        self.first_line = first_line
        self.last_line = last_line
        self.is_new = is_new

    def __repr__(self):
        return "Location(%d-%d @ %r)" % (self.first_line, self.last_line, self.sha1)

    def __str__(self):
        return self.sha1

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return str(self) == str(other)

    async def __find_filediff(self, from_commit, to_commit):
        changeset = await api.changeset.fetch(
            from_commit.critic, from_commit=from_commit, to_commit=to_commit
        )

        # We will only be looking at direct changesets that should be created
        # immediately when the commits were added to the review. Thus it should
        # be safe to assume they are always available immediately.
        assert "changedlines" in await changeset.completion_level, "%s..%s" % (
            from_commit.sha1,
            to_commit.sha1,
        )

        try:
            return await api.filediff.fetch(
                await api.filechange.fetch(changeset, self.file)
            )
        except api.filechange.InvalidId:
            return None

    async def translate_forwards(self, parent_commit, child_commit):
        """Return a forward translated location, or None

           "Forward" means the location is assumed to be in the old side of the
           diff, and should be translated to the new side.

           If any block of changed lines overlap this location's lines, None is
           returned."""

        filediff = await self.__find_filediff(parent_commit, child_commit)

        if not filediff:
            # The file was apparently not modified in between these commits. The
            # same location is thus still valid.
            return self

        delta = old_offset = 0

        for lines in await filediff.changed_lines:
            first_affected = old_offset + lines.offset
            first_unaffected = first_affected + lines.delete_length
            if first_unaffected <= self.first_line:
                # Change is before (and does not overlap) the location.
                delta += lines.insert_count - lines.delete_count
                old_offset = first_unaffected
            elif first_affected <= self.last_line:
                # Change overlaps the location.
                logger.debug(
                    "forwards %s..%s: comment=%d-%d, overlapping chunk=%d-%d",
                    parent_commit.sha1[:8],
                    child_commit.sha1[:8],
                    self.first_line,
                    self.last_line,
                    first_affected,
                    first_unaffected - 1,
                )
                return None
            else:
                # Change is after the location, meaning, since changes come in
                # ascending offset order, that all other changes are also after
                # the location.
                break

        return Location(
            self.file,
            filediff.filechange.new_sha1,
            self.first_line + delta,
            self.last_line + delta,
        )

    async def translate_backwards(self, parent_commit, child_commit):
        """Return a backwards translated location, or None

           "Backwards" means the location is assumed to be in the old side of
           the diff, and should be translated to the new side.

           If any block of changed lines overlap this location's lines, None is
           returned."""

        # Note: This function translates from commit A to commit B via the
        #       changeset |B..A|. We could of course have used the changeset
        #       |A..B| instead, and the code in |translate_forwards()|. But such
        #       reversed changesets are not typically cached, and certainly not
        #       guaranteed to be cached, so a bit of code duplication is better.
        filediff = await self.__find_filediff(parent_commit, child_commit)

        if not filediff:
            # The file was apparently not modified in between these commits. The
            # same location is thus still valid.
            return self

        delta = new_offset = 0

        for lines in await filediff.changed_lines:
            first_affected = new_offset + lines.offset
            first_unaffected = first_affected + lines.insert_length
            if first_unaffected <= self.first_line:
                # Change is before (and does not overlap) the location.
                delta += lines.delete_count - lines.insert_count
                new_offset = first_unaffected
            elif first_affected <= self.last_line:
                # Change overlaps the location.
                logger.debug(
                    "backwards %s..%s: comment=%d-%d, overlapping chunk=%d-%d",
                    parent_commit.sha1[:8],
                    child_commit.sha1[:8],
                    self.first_line,
                    self.last_line,
                    first_affected,
                    first_unaffected - 1,
                )
                return None
            else:
                # Change is after the location, meaning, since changes come in
                # ascending offset order, that all other changes are also after
                # the location.
                break

        return Location(
            self.file,
            filediff.filechange.old_sha1,
            self.first_line + delta,
            self.last_line + delta,
        )

    @staticmethod
    async def fromAPI(api_location):
        file_information = await api_location.file_information
        return Location(
            file_information.file,
            file_information.sha1,
            api_location.first_line - 1,
            api_location.last_line - 1,
        )


class PropagationResult:
    def __init__(self, locations):
        self.locations = set(locations)
        self.addressed_by = None

    def __repr__(self):
        return "PropagationResult(locations=%r, addressed_by=%r)" % (
            self.locations,
            self.addressed_by,
        )


class PropagateInCommitSet:
    def __init__(self, commits, file, existing_locations={}):
        self.commits = commits
        self.file = file
        self.locations = {}  # {location => location}
        self.final_locations = {}  # {commit => location}
        self.__addressed_by = set()
        self.__processed = set()

        for sha1, (first_line, last_line) in existing_locations.items():
            self.add_location(sha1, first_line - 1, last_line - 1)

    def add_location(self, sha1, first_line, last_line):
        return self.__add_location(
            Location(self.file, sha1, first_line, last_line, is_new=False)
        )

    def __add_location(self, location):
        if not location:
            return location
        return self.locations.setdefault(location, location)

    async def __child_location(self, commit, location, child):
        try:
            file_information = await child.getFileInformation(self.file)
            sha1 = file_information.sha1 if file_information else None
        except api.commit.NotAFile:
            sha1 = None
        if sha1 in self.locations:
            return self.locations[sha1]
        return self.__add_location(
            await location.translate_forwards(parent_commit=commit, child_commit=child)
        )

    async def forwards(self, commit, location):
        if not location:
            logger.debug("propagate forwards: %s (N/A)", commit.sha1[:8])
            self.__addressed_by.add(commit)
            return

        logger.debug(
            "propagate forwards: %s (%d-%d)",
            commit.sha1[:8],
            location.first_line,
            location.last_line,
        )

        self.__processed.add(commit)

        if commit in self.commits.heads:
            logger.debug("  - reached head of commit-set")
            self.final_locations[commit] = location
        else:
            for child in self.commits.getChildrenOf(commit):
                logger.debug("  child: %s", child.sha1[:8])
                if child in self.__processed:
                    logger.debug("  - already processed")
                    continue
                await self.forwards(
                    child, await self.__child_location(commit, location, child)
                )

        # Also do backwards propagation. We won't go back up the same path we
        # got here, due to |self.__processed| checks, so we will only go back up
        # via other parents of merge commits.
        if commit in self.commits:
            await self.backwards(commit, location)

    async def __parent_location(self, commit, location, parent):
        try:
            file_information = await parent.getFileInformation(self.file)
            sha1 = file_information.sha1 if file_information else None
        except api.commit.NotAFile:
            sha1 = None
        if sha1 in self.locations:
            return self.locations[sha1]
        return self.__add_location(
            await location.translate_backwards(
                parent_commit=parent, child_commit=commit
            )
        )

    async def backwards(self, commit, location):
        if not location:
            logger.debug("propagate backwards: %s (N/A)", commit.sha1[:8])
            return

        logger.debug(
            "propagate backwards: %s (%d-%d)",
            commit.sha1[:8],
            location.first_line,
            location.last_line,
        )

        self.__processed.add(commit)

        for parent in await commit.parents:
            logger.debug("  parent: %s", parent.sha1[:8])
            if parent in self.__processed:
                logger.debug("  - already processed")
                continue
            parent_location = await self.__parent_location(commit, location, parent)
            if parent in self.commits.tails:
                if parent_location:
                    logger.debug("  - reached tail of commit-set")
                    self.final_locations[parent] = parent_location
                continue
            assert parent in self.commits, repr(
                (parent, self.commits, self.commits.tails)
            )
            await self.backwards(parent, parent_location)

    @property
    def addressed_by(self):
        if len(self.__addressed_by) == 1:
            (addressed_by,) = self.__addressed_by
            return addressed_by
        else:
            # More than one commit changed these lines. This can happen if the
            # branch splits where the comment exists, and then both sides change
            # the lines, and are later merged together. We arbitrarily pick the
            # commit in |added_commits| that comes first in topological order.
            for commit in self.commits.topo_ordered:
                if commit in self.__addressed_by:
                    return commit
            assert not "reached"


async def propagate_in_new_commits(critic, location, existing_locations, added_commits):
    """Propagate the comment into the added commits

       The comment must have been translated to the current tip of the review
       branch, meaning its FileVersionLocations's |commit| attribute must be
       that commit.

       Returns a PropagationResult object."""

    commit = await location.commit

    assert commit in added_commits.tails

    propagate = PropagateInCommitSet(
        added_commits, await location.file, existing_locations
    )

    await propagate.forwards(commit, await Location.fromAPI(location))

    result = PropagationResult(propagate.locations)

    if not propagate.final_locations:
        result.addressed_by = propagate.addressed_by

    return result


async def propagate_new_comment(
    review, comment_location=None, *, existing_locations={}
):
    """Propagate a new comment to other commits in the review

       Returns a PropagationResult object."""

    file = await comment_location.file

    # Retrieve the "primary commented commit" which is the commit whose version
    # of the file the author of the comment actually selected lines from.
    commit = await comment_location.commit
    if not commit:
        changeset = await comment_location.changeset
        if comment_location.side == "old":
            commit = await changeset.from_commit
        else:
            commit = await changeset.to_commit

    location = await Location.fromAPI(comment_location)

    # Find the partition containing the primary commented commit.
    partition = await review.first_partition
    while True:
        if commit in partition.commits or commit in partition.commits.tails:
            break
        partition = partition.following.partition

    primary_partition = partition

    result = PropagationResult({location})
    final_locations = {}

    # Propagate forwards first, to determine whether the comment is active or
    # "addressed".
    while True:
        if partition.commits:
            propagate = PropagateInCommitSet(
                partition.commits, file, existing_locations
            )

            await propagate.forwards(commit, location)

            result.locations.update(propagate.locations)
            final_locations.update(propagate.final_locations)

            if partition.commits.heads.difference(propagate.final_locations):
                result.addressed_by = propagate.addressed_by
                break

        edge = partition.preceding
        if not edge:
            break

        rebase = edge.rebase
        branchupdate = await rebase.branchupdate

        if rebase.type == "move":
            location = await location.translate_forwards(
                parent_commit=await branchupdate.from_head,
                child_commit=await branchupdate.to_head,
            )

            if not location:
                result.addressed_by = (await rebase.equivalent_merge) or (
                    await rebase.replayed_rebase
                )
                break

        partition = edge.partition
        commit = await branchupdate.to_head

    # Also propagate backwards. This does not affect the comment's state.
    edge = primary_partition.following
    while edge:
        rebase = edge.rebase
        branchupdate = await rebase.branchupdate

        if rebase.type == "move":
            location = await location.translate_backwards(
                parent_commit=await branchupdate.from_head,
                child_commit=await branchupdate.to_head,
            )
        else:
            location = final_locations.get(await branchupdate.to_head)

        if not location:
            break

        final_locations[await branchupdate.from_head] = location

        commits = edge.partition.commits
        if commits:
            (commit,) = commits.heads
            location = final_locations.get(commit)

            if not location:
                break

            propagate = PropagateInCommitSet(commits, file, existing_locations)

            await propagate.backwards(commit, location)

            result.locations.update(propagate.locations)
            final_locations.update(propagate.final_locations)

        edge = edge.partition.following

    return result
