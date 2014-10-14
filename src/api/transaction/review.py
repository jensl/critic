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

import api

import dbutils
import gitutils

from reviewing.comment.propagate import Propagation

class ModifyReview(object):
    def __init__(self, transaction, review):
        self.transaction = transaction
        self.review = review

    def createComment(self, comment_type, author, text, location, callback):
        assert comment_type in api.comment.Comment.TYPE_VALUES
        assert isinstance(author, api.user.User)
        assert isinstance(text, str)

        critic = self.transaction.critic

        # Users are not (generally) allowed to create comments as other users.
        api.PermissionDenied.raiseUnlessUser(critic, author)

        side = file_id = first_commit_id = last_commit_id = lines = None

        if isinstance(location, api.comment.CommitMessageLocation):
            first_commit_id = last_commit_id = location.commit.id
            # FIXME: Make commit message comment line numbers one-based too!
            lines = [(location.commit.sha1, (location.first_line - 1,
                                             location.last_line - 1))]
            # FIXME: ... and then delete the " - 1" from the above two lines.
        elif isinstance(location, api.comment.FileVersionLocation):
            # Propagate the comment using "legacy" comment propagation helper.

            if location.changeset:
                if location.side == "old":
                    commit = location.changeset.from_commit
                else:
                    commit = location.changeset.to_commit
                side = location.side
                first_commit_id = location.changeset.from_commit.id
                last_commit_id = location.changeset.to_commit.id
            else:
                commit = location.commit
                first_commit_id = last_commit_id = location.commit.id

            legacy_review = dbutils.Review.fromAPI(self.review)
            legacy_commit = gitutils.Commit.fromAPI(commit)

            propagation = Propagation(critic.database)
            propagation.setCustom(
                legacy_review, legacy_commit, location.file.id,
                location.first_line, location.last_line)
            propagation.calculateInitialLines()

            file_id = location.file.id
            lines = propagation.all_lines.items()

        comment = CreatedComment(critic, self.review)
        initial_comment = api.transaction.LazyObject()

        def collectInitialComment(comment_id):
            initial_comment_id.append(comment_id)

        self.transaction.tables.update(("commentchains", "comments"))
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO commentchains (review, uid, type, origin, file,
                                         first_commit, last_commit)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id""",
                (self.review.id, author.id, comment_type, side, file_id,
                 first_commit_id, last_commit_id),
                collector=comment))
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO comments (chain, uid, state, comment)
                   VALUES (%s, %s, 'draft', %s)
                RETURNING id""",
                (comment.id, author.id, text),
                collector=initial_comment))
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE commentchains
                      SET first_comment=%s
                    WHERE id=%s""",
                (initial_comment.id, comment.id)))

        if lines:
            self.transaction.tables.add("commentchainlines")
            self.transaction.items.append(
                api.transaction.Query(
                    """INSERT
                         INTO commentchainlines (chain, uid, sha1,
                                                 first_line, last_line)
                       VALUES (%s, %s, %s, %s, %s)""",
                    *((comment.id, author.id, sha1, first_line, last_line)
                      for sha1, (first_line, last_line) in lines)))

        if callback:
            self.transaction.callbacks.append(
                lambda: callback(comment.fetch()))

        return comment

    def modifyComment(self, comment):
        from comment import ModifyComment
        assert comment.review == self.review

        # Users are not (generally) allowed to modify other users' comments.
        api.PermissionDenied.raiseUnlessUser(self.transaction.critic,
                                             comment.author)

        return ModifyComment(self.transaction, comment)

class CreatedComment(api.transaction.LazyAPIObject):
    def __init__(self, critic, review, callback=None):
        super(CreatedComment, self).__init__(
            critic, api.comment.fetch, callback)
        self.review = review
