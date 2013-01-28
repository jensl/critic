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

import dbutils

from changeset.utils import createChangeset

FORWARD  = 1
BACKWARD = 2

class Location:
    def __init__(self, first_line, last_line, active=True):
        self.first_line = first_line
        self.last_line = last_line
        self.active = active

    def copy(self):
        return Location(self.first_line, self.last_line, self.active)

    def __iadd__(self, delta):
        self.first_line += delta
        self.last_line += delta
        return self

    def __len__(self):
        return 2

    def __getitem__(self, index):
        if index == 0: return self.first_line
        elif index == 1: return self.last_line
        else: raise IndexError

    def __eq__(self, other):
        return tuple(self) == tuple(other)

    def apply(self, changes, direction):
        """
        Apply a set of changes and adjust the location accordingly.

        Process a set of changes in the form of a list of objects with the
        attributes delete_offset, delete_count, insert_offset and insert_count
        (such as diff.Chunk objects) sorted on ascending offsets.  If any of the
        changes overlap this location, the location's 'active' attribute is set
        to False, otherwise the 'first_line' and 'last_line' attributes are
        adjusted to keep the location referencing the same lines.

        If the 'direction' argument is FORWARD, this location is interpreted as
        a location in the old version (before the changes) and is adjusted to a
        location in the new version (after the changes.)  If the argument is
        BACKWARD, this location is interpreted as a location in the new version
        (after the changes) and is adjusted to a location in the old version
        (before the changes.)

        Returns True if the location is still active.
        """

        delta = 0

        # The only difference between the two loops is that uses of
        # delete_offset/delete_count and insert_offset/insert_count are
        # mirrored.
        if direction == FORWARD:
            for change in changes:
                if change.delete_offset + change.delete_count <= self.first_line:
                    # Change is before (and does not overlap) the location.
                    delta += change.insert_count - change.delete_count
                elif change.delete_offset <= self.last_line:
                    # Change overlaps the location.
                    self.active = False
                    break
                else:
                    # Change is after the location, meaning, since changes come
                    # in ascending offset order, that all other changes are also
                    # after the location.
                    break
        else:
            for change in changes:
                if change.insert_offset + change.insert_count <= self.first_line:
                    # Change is before (and does not overlap) the location.
                    delta += change.delete_count - change.insert_count
                elif change.insert_offset <= self.last_line:
                    # Change overlaps the comment chain.
                    self.active = False
                    break
                else:
                    # Change is after the location, meaning, since changes come
                    # in ascending offset order, that all other changes are also
                    # after the location.
                    break

        # Apply 'delta' to the location if it's still active.
        if self.active: self += delta

        return self.active

class AddressedBy(object):
    def __init__(self, parent, child, location):
        self.parent = parent
        self.child = child
        self.location = location

class Propagation:
    def __init__(self, db):
        self.db = db
        self.review = None
        self.rebases = None
        self.initial_commit = None
        self.file_path = None
        self.file_id = None
        self.location = None
        self.active = None
        self.all_lines = None
        self.new_lines = None

    def setCustom(self, review, commit, file_id, first_line, last_line):
        """
        Initialize for propagation of a custom location.

        This mode of operation is used to propagate a new comment chain to all
        relevant commits current part of the review.

        Returns false if the creating a comment at the specified location is not
        supported, typically because the commit is not being reviewed in the
        review.
        """

        if not review.containsCommit(self.db, commit, True):
            return False

        self.review = review
        self.rebases = review.getReviewRebases(self.db)
        self.initial_commit = commit
        self.addressed_by = []
        self.file_path = dbutils.describe_file(self.db, file_id)
        self.file_id = file_id
        self.location = Location(first_line, last_line)
        self.active = True

        file_sha1 = commit.getFileSHA1(self.file_path)

        self.all_lines = { file_sha1: (first_line, last_line) }
        self.new_lines = { file_sha1: (first_line, last_line) }

        return True

    def setExisting(self, review, chain_id, commit, file_id, first_line, last_line, reopening=False):
        """
        Initialize for propagation of existing comment chain.

        This initializes the location to where the comment chain is located in
        the most recent commit in the review.  If the comment chain is not
        present in the most recent commit in the review, this function returns
        False.

        This mode of operation is used to update existing comment chains when
        adding new commits to a review.
        """

        self.review = review
        self.rebases = review.getReviewRebases(self.db)
        self.initial_commit = commit
        self.addressed_by = []
        self.file_path = dbutils.describe_file(self.db, file_id)
        self.file_id = file_id
        self.location = Location(first_line, last_line)
        self.active = True
        self.all_lines = {}
        self.new_lines = {}

        cursor = self.db.cursor()
        cursor.execute("""SELECT sha1, first_line, last_line
                            FROM commentchainlines
                           WHERE chain=%s""",
                       (chain_id,))

        for file_sha1, first_line, last_line in cursor:
            self.all_lines[file_sha1] = (first_line, last_line)

        if reopening:
            self.__setLines(commit.getFileSHA1(self.file_path), self.location)

        return True

    def calculateInitialLines(self):
        """
        Calculate the initial set of line mappings for a comment chain.

        Propagates the initial location both backward and forward through all
        current commits in the review.  If, through forward propagation, the
        location becomes inactive, the 'active' attribute is set to False.  In
        any case, the 'lines' attribute will map each file SHA-1 to a pair of
        line numbers (first_line, last_line) for each location found during the
        propagation.

        Returns the value of the 'active' attribute.
        """

        self.__propagate(self.review.getCommitSet(self.db))
        return self.active

    def calculateAdditionalLines(self, commits):
        """
        Calculate additional set of line mappings when adding new commits.

        If this propagation object is not active (because the comment chain
        it represents is not present in the most recent commit in the review)
        then nothing happens.

        Returns the value of the 'active' attribute.
        """

        self.__propagate(commits)
        return self.active

    def __propagate(self, commits):
        cursor = self.db.cursor()

        def propagateBackward(commit, location, processed):
            parents = commits.getParents(commit)
            recurse = []

            if not parents:
                for parent_sha1 in commit.parents:
                    rebase = self.rebases.fromNewHead(parent_sha1)
                    if rebase:
                        parents.add(rebase.old_head)

            for parent in parents - processed:
                changes = self.__getChanges(parent, commit)
                if changes:
                    parent_location = location.copy()
                    if parent_location.apply(changes, BACKWARD):
                        file_sha1 = parent.getFileSHA1(self.file_path)
                        assert file_sha1
                        self.__setLines(file_sha1, parent_location)
                        recurse.append((parent, parent_location))
                else:
                    recurse.append((parent, location))

            processed.add(commit)

            for parent, parent_location in recurse:
                propagateBackward(parent, parent_location, processed)

        def propagateForward(commit, location, processed):
            children = commits.getChildren(commit)
            recurse = []

            if not children:
                rebase = self.rebases.fromOldHead(commit)
                if rebase:
                    children.update(commits.getChildren(rebase.new_head))

            if not children:
                assert not commits or commit in commits.getHeads() or self.rebases.fromNewHead(commit)
                self.active = True

            for child in children - processed:
                changes = self.__getChanges(commit, child)
                if changes:
                    child_location = location.copy()
                    if child_location.apply(changes, FORWARD):
                        file_sha1 = child.getFileSHA1(self.file_path)
                        assert file_sha1
                        self.__setLines(file_sha1, child_location)
                        recurse.append((child, child_location))
                    else:
                        self.addressed_by.append(AddressedBy(commit, child, location))
                else:
                    recurse.append((child, location))

            processed.add(commit)

            for child, child_location in recurse:
                propagateForward(child, child_location, processed)

            # If we started propagation in the middle of, or at the end of, the
            # commit-set, this call does the main backward propagation.  After
            # that, it will do extra backward propagation via other parents of
            # merge commits encountered during forward propagation.
            #
            # For non-merge commits, 'processed' will always contain the single
            # parent of 'commit', and propagateBackward() will find no parent
            # commits to process, leaving this call a no-op.
            propagateBackward(commit, location, processed)

        # Will be set to True again if propagation reaches the head of the
        # commit-set.
        self.active = False

        propagateForward(self.initial_commit, self.location, set())

    def __getChanges(self, from_commit, to_commit):
        changesets = createChangeset(self.db,
                                     user=None,
                                     repository=self.review.repository,
                                     from_commit=from_commit,
                                     to_commit=to_commit,
                                     filtered_file_ids=set([self.file_id]),
                                     do_highlight=False)

        assert len(changesets) == 1

        if changesets[0].files:
            assert changesets[0].files[0].id == self.file_id
            return changesets[0].files[0].chunks
        else:
            return None

    def __setLines(self, file_sha1, lines):
        if file_sha1 not in self.all_lines:
            self.all_lines[file_sha1] = self.new_lines[file_sha1] = tuple(lines)
        else:
            assert self.all_lines[file_sha1] == tuple(lines)
