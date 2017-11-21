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

    def createComment(self, comment_type, author, text, location=None,
                      callback=None):
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
            lines = list(propagation.all_lines.items())

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
        from .comment import ModifyComment
        assert comment.review == self.review

        # Users are not (generally) allowed to modify other users' draft
        # comments.
        if comment.is_draft:
            api.PermissionDenied.raiseUnlessUser(self.transaction.critic,
                                                 comment.author)

        return ModifyComment(self.transaction, comment)

    def prepareRebase(self, user, new_upstream=None, history_rewrite=None, branch=None, callback=None):
        assert isinstance(user, api.user.User)
        assert new_upstream is None or isinstance(new_upstream, str)
        assert history_rewrite is None or isinstance(history_rewrite, bool)
        assert (new_upstream is None) != (history_rewrite is None)
        assert callback is None or callable(callback)

        pending = self.review.pending_rebase
        if pending is not None:
            creator = pending.creator
            raise api.log.rebase.RebaseError(
                "The review is already being rebased by %s <%s>." %
                (creator.fullname, creator.email if creator.email is not None
                 else "email missing"))

        commitset = self.review.branch.commits
        tails = commitset.filtered_tails
        heads = commitset.heads

        assert len(heads) == 1
        head = next(iter(heads))

        old_upstream_id = None
        new_upstream_id = None

        if new_upstream is not None:
            if len(tails) > 1:
                raise api.log.rebase.RebaseError(
                    "Rebase of branch with multiple tails, to new upstream "
                    "commit, is not supported.")

            tail = next(iter(tails))
            old_upstream_id = tail.id

            if new_upstream == "0" * 40:
                new_upstream_id = None
            else:
                if not gitutils.re_sha1.match(new_upstream):
                    cursor = self.transaction.critic.getDatabaseCursor()
                    cursor.execute("SELECT sha1 FROM tags WHERE repository=%s AND name=%s",
                                   (self.review.repository.id, new_upstream))
                    row = cursor.fetchone()
                    if row:
                        new_upstream_arg = row[0]
                    else:
                        raise api.log.rebase.RebaseError(
                            "Specified new_upstream is invalid.")
                try:
                    new_upstream_commit = api.commit.fetch(
                        self.review.repository, ref=new_upstream)
                except:
                    raise api.log.rebase.RebaseError(
                        "The specified new upstream commit does not exist "
                        "in Critic's repository")
                new_upstream_id = new_upstream_commit.id

        rebase = CreatedRebase(self.transaction.critic, self.review)

        self.transaction.tables.add("reviewrebases")
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO reviewrebases (review, old_head, new_head, old_upstream, new_upstream, uid, branch)
                   VALUES (%s, %s, NULL, %s, %s, %s, %s)
                RETURNING id""",
                (self.review.id, head.id, old_upstream_id, new_upstream_id, user.id, branch),
                collector=rebase))

        if callback:
            self.transaction.callbacks.append(
                lambda: callback(rebase.fetch()))

    def cancelRebase(self, rebase):
        self.transaction.tables.add("reviewrebases")
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM reviewrebases
                    WHERE review=%s
                      AND new_head IS NULL
                      AND id=%s""",
                (self.review.id, rebase.id)))

    def submitChanges(self, batch_comment, callback):
        critic = self.transaction.critic

        unpublished_changes = api.batch.fetchUnpublished(critic, self.review)

        if unpublished_changes.is_empty:
            raise api.batch.BatchError("No unpublished changes to submit")

        created_comments = []
        empty_comments = []

        if batch_comment:
            created_comments.append(batch_comment)

        for comment in unpublished_changes.created_comments:
            if comment.text.strip():
                created_comments.append(comment)
            else:
                empty_comments.append(comment)

        batch = CreatedBatch(critic, self.review)

        self.transaction.tables.add("batches")
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO batches (review, uid, comment)
                   VALUES (%s, %s, %s)
                RETURNING id""",
                (self.review.id, critic.actual_user.id,
                 batch_comment.id if batch_comment else None),
                collector=batch))

        def ids(api_objects):
            return [api_object.id for api_object in api_objects]

        self.transaction.tables.add("commentchains")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE commentchains
                      SET state='open',
                          batch=%s
                    WHERE id=ANY (%s)""",
                (batch.id, ids(created_comments))))
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM commentchains
                    WHERE id=ANY (%s)""",
                (ids(empty_comments),)))

        self.transaction.tables.add("comments")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE comments
                      SET state='current',
                          batch=%s
                    WHERE id IN (SELECT first_comment
                                   FROM commentchains
                                  WHERE id=ANY (%s))""",
                (batch.id, ids(created_comments))))
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE comments
                      SET state='current',
                          batch=%s
                    WHERE id=ANY (%s)""",
                (batch.id, ids(unpublished_changes.written_replies))))

        self.transaction.tables.add("commentchainlines")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE commentchainlines
                      SET state='current'
                    WHERE chain=ANY (%s)""",
                (ids(created_comments),)))

        # Lock all rows in |commentchains| that we may want to update.
        self.transaction.items.append(
            api.transaction.Query(
                """SELECT 1
                     FROM commentchains
                    WHERE id=ANY (%s)
                      FOR UPDATE""",
                (ids(unpublished_changes.resolved_issues) +
                 ids(unpublished_changes.reopened_issues) +
                 ids(unpublished_changes.morphed_comments.keys()),)))

        # Mark valid comment state changes as performed.
        self.transaction.tables.add("commentchainchanges")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE commentchainchanges
                      SET batch=%s,
                          state='performed'
                    WHERE uid=%s
                      AND state='draft'
                      AND chain IN (SELECT id
                                      FROM commentchains
                                     WHERE id=ANY (%s)
                                       AND type='issue'
                                       AND state=%s)""",
                (batch.id, critic.actual_user.id,
                 ids(unpublished_changes.resolved_issues), "open"),
                (batch.id, critic.actual_user.id,
                 ids(unpublished_changes.reopened_issues), "closed"))) # FIXME: handle |state='addressed'|

        # Mark valid comment type changes as performed.
        morphed_to_issue = []
        morphed_to_note = []
        for comment, new_type in unpublished_changes.morphed_comments.items():
            if new_type == "issue":
                morphed_to_issue.append(comment)
            else:
                morphed_to_note.append(comment)
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE commentchainchanges
                      SET batch=%s,
                          state='performed'
                    WHERE uid=%s
                      AND state='draft'
                      AND chain IN (SELECT id
                                      FROM commentchains
                                     WHERE id=ANY (%s)
                                       AND type=%s)""",
                (batch.id, critic.actual_user.id, ids(morphed_to_issue),
                 "note"),
                (batch.id, critic.actual_user.id, ids(morphed_to_note),
                 "issue")))

        # Actually perform state changes marked as valid above.
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE commentchains
                      SET state=%s,
                          closed_by=%s
                    WHERE id IN (SELECT chain
                                   FROM commentchainchanges
                                  WHERE batch=%s
                                    AND state='performed'
                                    AND to_state=%s)""",
                ("closed", critic.actual_user.id, batch.id, "closed"),
                ("open", None, batch.id, "open")))

        # Actually perform type changes marked as valid above.
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE commentchains
                      SET type=%s
                    WHERE id IN (SELECT chain
                                   FROM commentchainchanges
                                  WHERE batch=%s
                                    AND state='performed'
                                    AND to_type=%s)""",
                ('issue', batch.id, 'issue'),
                ('note', batch.id, 'note')))

        # Lock all rows in |reviewfiles| that we may want to update.
        self.transaction.tables.add("reviewfilechanges")
        self.transaction.items.append(
            api.transaction.Query(
                """SELECT 1
                     FROM reviewfiles
                    WHERE id=ANY (%s)
                      FOR UPDATE""",
                (ids(unpublished_changes.reviewed_file_changes) +
                 ids(unpublished_changes.unreviewed_file_changes),)))

        # Mark valid draft changes as "performed".
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE reviewfilechanges
                      SET batch=%s,
                          state='performed'
                    WHERE uid=%s
                      AND state='draft'
                      AND file IN (SELECT id
                                     FROM reviewfiles
                                    WHERE id=ANY (%s)
                                      AND state=%s)""",
                (batch.id, critic.actual_user.id,
                 ids(unpublished_changes.reviewed_file_changes),
                 "pending"),
                (batch.id, critic.actual_user.id,
                 ids(unpublished_changes.unreviewed_file_changes),
                 "reviewed")))

        # Actually perform all the changes we previously marked as performed.
        self.transaction.tables.add("reviewfiles")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE reviewfiles
                      SET state=%s,
                          reviewer=%s
                    WHERE id IN (SELECT file
                                   FROM reviewfilechanges
                                  WHERE batch=%s
                                    AND state='performed'
                                    AND to_state=%s)""",
                ('reviewed', critic.actual_user.id, batch.id, 'reviewed'),
                ('pending', None, batch.id, 'pending')))

        if callback:
            self.transaction.callbacks.append(
                lambda: callback(batch.fetch()))

        return batch

    def markChangeAsReviewed(self, filechange):
        assert isinstance(filechange,
                          api.reviewablefilechange.ReviewableFileChange)

        critic = self.transaction.critic

        if filechange.draft_changes:
            current_state = filechange.draft_changes.new_is_reviewed
        else:
            current_state = filechange.is_reviewed
        if current_state:
            raise api.reviewablefilechange.ReviewableFileChangeError(
                "Specified file change is already marked as reviewed")

        if critic.actual_user not in filechange.assigned_reviewers:
            raise api.reviewablefilechange.ReviewableFileChangeError(
                "Specified file change is not assigned to current user")

        self.transaction.tables.add("reviewfilechanges")

        if filechange.draft_changes:
            self.transaction.items.append(
                api.transaction.Query(
                    """DELETE
                         FROM reviewfilechanges
                        WHERE file=%s
                          AND uid=%s
                          AND to_state='pending'""",
                    (filechange.id, critic.actual_user.id)))

        if not filechange.is_reviewed:
            self.transaction.items.append(
                api.transaction.Query(
                    """INSERT
                         INTO reviewfilechanges (file, uid, from_state,
                                                 to_state)
                       VALUES (%s, %s, 'pending', 'reviewed')""",
                    (filechange.id, critic.actual_user.id)))

    def markChangeAsPending(self, filechange):
        assert isinstance(filechange,
                          api.reviewablefilechange.ReviewableFileChange)

        critic = self.transaction.critic

        if filechange.draft_changes:
            current_state = filechange.draft_changes.new_is_reviewed
        else:
            current_state = filechange.is_reviewed
        if not current_state:
            raise api.reviewablefilechange.ReviewableFileChangeError(
                "Specified file change is already marked as pending")

        if critic.actual_user not in filechange.assigned_reviewers:
            raise api.reviewablefilechange.ReviewableFileChangeError(
                "Specified file change is not assigned to current user")

        self.transaction.tables.add("reviewfilechanges")

        if filechange.draft_changes:
            self.transaction.items.append(
                api.transaction.Query(
                    """DELETE
                         FROM reviewfilechanges
                        WHERE file=%s
                          AND uid=%s
                          AND to_state='reviewed'""",
                    (filechange.id, critic.actual_user.id)))

        if filechange.is_reviewed:
            self.transaction.items.append(
                api.transaction.Query(
                    """INSERT
                         INTO reviewfilechanges (file, uid, from_state,
                                                 to_state)
                       VALUES (%s, %s, 'reviewed', 'pending')""",
                    (filechange.id, critic.actual_user.id)))

class CreatedComment(api.transaction.LazyAPIObject):
    def __init__(self, critic, review, callback=None):
        super(CreatedComment, self).__init__(
            critic, api.comment.fetch, callback)
        self.review = review

class CreatedRebase(api.transaction.LazyAPIObject):
    def __init__(self, critic, review, callback=None):
        super(CreatedRebase, self).__init__(
            critic, api.log.rebase.fetch, callback)
        self.review = review

class CreatedBatch(api.transaction.LazyAPIObject):
    def __init__(self, critic, review):
        super(CreatedBatch, self).__init__(critic, api.batch.fetch)
        self.review = review
