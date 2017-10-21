# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2016 the Critic contributors, Opera Software ASA
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

import sys
import installation

# Handles command line arguments and sets uid/gid.
installation.utils.start_migration()

dbschema = installation.utils.DatabaseSchema()

# New definitions in dbschema.git.sql.
dbschema.update("""

CREATE INDEX branches_base
          ON branches (base);

-- Branch updates:
--   One row per update (ff or not) of a branch.
CREATE TABLE branchupdates
  ( id SERIAL PRIMARY KEY,

    -- The branch that was updated.
    branch INTEGER NOT NULL REFERENCES branches ON DELETE CASCADE,
    -- User that performed the update.  NULL means the update was performed by
    -- the system (e.g. the branch tracker) rather than by a user.
    updater INTEGER REFERENCES users,
    -- Previous value of |branches.head|.  NULL means the branch was created.
    from_head INTEGER REFERENCES commits,
    -- New value of |branches.head|.
    to_head INTEGER NOT NULL REFERENCES commits,
    -- Previous value of |branches.base|.
    from_base INTEGER REFERENCES branches ON DELETE SET NULL,
    -- New value of |branches.base|.
    to_base INTEGER REFERENCES branches ON DELETE SET NULL,
    -- Previous value of |branches.tail|.
    from_tail INTEGER REFERENCES commits,
    -- New value of |branches.tail|.
    to_tail INTEGER REFERENCES commits,
    -- When the update was performed.
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    -- Output, displayed in logs and also echoed by the post-receive hook if the
    -- update is performed via Git.
    output TEXT );
CREATE INDEX branchupdates_branch_to_from
          ON branchupdates (branch, to_head, from_head);
CREATE INDEX branchupdates_from_base
          ON branchupdates (from_base);
CREATE INDEX branchupdates_to_base
          ON branchupdates (to_base);

-- Branch commits:
--   One row per commit associated with a branch.
--
-- Note that this does not (typically) mean "all reachable commits",
-- since then most commits would be associated with most branches in a
-- repository with a long history.
CREATE TABLE branchcommits
  ( branch INTEGER NOT NULL REFERENCES branches ON DELETE CASCADE,
    commit INTEGER NOT NULL REFERENCES commits,

    PRIMARY KEY (branch, commit) );
CREATE INDEX branchcommits_commit
          ON branchcommits (commit);

-- Branch update commits:
--   One row per commit (dis)associated with a branch by an update.
--
-- This table documents the changes to the |branchcommits| table by each branch
-- update.
CREATE TABLE branchupdatecommits
  ( branchupdate INTEGER NOT NULL REFERENCES branchupdates ON DELETE CASCADE,
    commit INTEGER NOT NULL REFERENCES commits,
    associated BOOLEAN NOT NULL,

    PRIMARY KEY (branchupdate, commit) );

CREATE TYPE pendingrefupdatestate AS ENUM
  ( -- Update has been approved by the pre-receive hook.  The ref in the Git
    -- repository may or may not have been updated, and may never be.
    'preliminary',
    -- Update has been processed by the branchupdater service, but was of a
    -- review branch and has yet to be processed by the reviewupdater service.
    'processed',
    -- Update has been processed by the branchupdater service, and the
    -- reviewupdater service if it was of a review branch.  Any output from the
    -- processing has been recorded in |pendingrefupdateoutputs| by this time.
    'finished',
    -- Update has been handled, but the handling failed due to an implementation
    -- error.
    'failed' );

-- Pending ref updates:
--   One row per pending update, deleted once fully processed.
--
-- This table stores raw SHA-1 sums instead of commit ids so that rows can be
-- inserted into it without first recording commits into the 'commits' table.
-- The recording of commits can be costly, so we prefer to do that in the
-- background instead of directly from the pre-receive hook.
CREATE TABLE pendingrefupdates
  ( id SERIAL PRIMARY KEY,

    -- User that is responsible for the update, or NULL if the system is
    -- performing the update.
    updater INTEGER REFERENCES users,
    -- Repository being updated.
    repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    -- Name of ref being updated.  This includes the "refs/.../" prefix (the ref
    -- being updated might not be a branch.)
    name VARCHAR(256) NOT NULL,
    -- Old value (SHA-1).  All zeroes means ref was created.
    old_sha1 CHAR(40) NOT NULL,
    -- New vaule (SHA-1).  All zeroes means ref was deleted.
    new_sha1 CHAR(40) NOT NULL,
    -- JSON encoded flags received from the Git hook.
    flags TEXT,
    -- State of the update.
    state pendingrefupdatestate NOT NULL DEFAULT 'preliminary',
    -- Timestamp.  Used to time out preliminary updates, for which the
    -- post-receive hook was seemingly never called.
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    -- Timestamp.  Used to clean up / revert finished and failed updates.
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    -- True if the post-receive hook has stopped waiting for the update to be
    -- processed.  Updates in this state are cleaned up by the branchupdate
    -- service, and the user notified by email in case of failure.
    abandoned BOOLEAN NOT NULL DEFAULT FALSE,
    -- Branch update record.  Is deleted when cleaning up the pending ref update
    -- in case of failure.
    branchupdate INTEGER REFERENCES branchupdates ON DELETE SET NULL );

CREATE INDEX pendingrefupdates_repository_name
          ON pendingrefupdates (repository, name);
CREATE INDEX pendingrefupdates_branchupdate
          ON pendingrefupdates (branchupdate);

-- Output associated with pending ref updates:
--   Zero or more rows per pending update, deleted along with the pending ref
--   update itself.
CREATE TABLE pendingrefupdateoutputs
  ( id SERIAL PRIMARY KEY,

    pendingrefupdate INTEGER NOT NULL REFERENCES pendingrefupdates ON DELETE CASCADE,
    output TEXT NOT NULL );

CREATE INDEX pendingrefupdateoutputs_pendingrefupdate
          ON pendingrefupdateoutputs (pendingrefupdate);

""")

# New definitions in dbschema.review.sql.
dbschema.update("""

-- Review branch updates:
--   One row per row in the 'branchupdates' table that refers to branches
--   connected with a review.
CREATE TABLE reviewupdates
  ( -- The branch update record.
    branchupdate INTEGER PRIMARY KEY REFERENCES branchupdates ON DELETE CASCADE,
    -- The review whose branch was updated.
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    -- Output, displayed in logs and also echoed by the post-receive hook if the
    -- update is performed via Git (after the regular branch update output.)
    output TEXT,
    -- Error message, if the update failed to be processed.  Since the validity
    -- of the branch update itself is checked before it happens, errors occuring
    -- at this stage are almost certainly implementation errors.
    --
    -- The error is displayed to administrators, and prevents repeated
    -- processing of the branch update (by way of inserting a review update
    -- record, despite the review not actually having been updated.)
    error TEXT );
CREATE INDEX reviewupdates_review
          ON reviewupdates (review);

""")

cursor = dbschema.db.cursor()

cursor.execute(
    """ALTER TABLE branches
        DROP CONSTRAINT IF EXISTS branches_base_fkey,
         ADD CONSTRAINT branches_base_fkey
           FOREIGN KEY (base) REFERENCES branches ON DELETE SET NULL""")

# Note: NOT NULL added later, after we've populated |reviewupdates|.
cursor.execute(
    """ALTER TABLE reviewchangesets
         ADD COLUMN branchupdate INTEGER
           REFERENCES reviewupdates ON DELETE CASCADE""")

cursor.execute(
    """CREATE INDEX reviewchangesets_branchupdate
                 ON reviewchangesets (branchupdate)""")

cursor.execute(
    """ALTER TABLE reviewrebases
         ADD COLUMN branchupdate INTEGER
           REFERENCES reviewupdates ON DELETE CASCADE""")

cursor.execute(
    """ALTER TABLE commentchains
         ADD addressed_by_update INTEGER
           REFERENCES branchupdates""")
cursor.execute(
    """CREATE INDEX commentchains_addressed_by_update
                 ON commentchains (addressed_by_update)""")

# Simply copy all rows from |reachable| to |branchcommits|.
cursor.execute("""INSERT
                    INTO branchcommits (branch, commit)
                  SELECT branch, commit
                    FROM reachable""")

# Insert a (mostly bogus) branch update for each branch except review branches
# that have been rebased, that is equivalent to the branch having just been
# created with its current value, by the system.
cursor.execute("""INSERT
                    INTO branchupdates (branch, to_head, to_base, to_tail)
                  SELECT branches.id, branches.head, branches.base,
                         branches.tail
                    FROM branches
         LEFT OUTER JOIN (SELECT reviews.branch AS branch,
                                 COUNT(reviewrebases.id)>0 AS is_rebased
                            FROM reviews
                 LEFT OUTER JOIN reviewrebases
                              ON (reviewrebases.review=reviews.id
                              AND reviewrebases.new_head IS NOT NULL)
                        GROUP BY reviews.branch
                         ) AS reviews ON (reviews.branch=branches.id)
                   WHERE reviews.branch IS NULL OR NOT reviews.is_rebased""")

# Insert matching review update for the mostly bogus branch updates.
cursor.execute("""INSERT
                    INTO reviewupdates (branchupdate, review)
                  SELECT branchupdates.id, reviews.id
                    FROM branchupdates
                    JOIN branches ON (branches.id=branchupdates.branch)
                    JOIN reviews ON (reviews.branch=branches.id)""")

# Set this mostly bogus branch update as each of the review's changesets
# branch update.
cursor.execute("""UPDATE reviewchangesets
                     SET branchupdate=branchupdates.id
                    FROM reviews, branchupdates
                   WHERE reviewchangesets.review=reviews.id
                     AND reviews.branch=branchupdates.branch""")

# Insert rows into the |branchupdatecommits| table indicating that all current
# commits on each non-review branch were added by the one branch update.
cursor.execute("""INSERT
                    INTO branchupdatecommits (branchupdate, commit, associated)
                  SELECT branchupdates.id, branchcommits.commit, TRUE
                    FROM branchupdates
                    JOIN branchcommits USING (branch)""")

# Find all rebases.
cursor.execute("""SELECT branches.id, branches.head,
                         reviews.id,
                         reviewrebases.id, reviewrebases.uid,
                         reviewrebases.old_head, reviewrebases.new_head,
                         reviewrebases.old_upstream,
                         reviewrebases.new_upstream,
                         reviewrebases.equivalent_merge,
                         reviewrebases.replayed_rebase
                    FROM branches
                    JOIN reviews ON (reviews.branch=branches.id)
                    JOIN reviewrebases ON (reviewrebases.review=reviews.id)
                   WHERE reviewrebases.new_head IS NOT NULL""")

reviews = {}
rebases = {}

for (branch_id, branch_head_id, review_id, rebase_id, updater_id,
     old_head_id, new_head_id, old_upstream_id, new_upstream_id,
     equivalent_merge_id, replayed_rebase_id) in cursor:
    _, _, review_rebases, _ = reviews.setdefault(
        review_id, (branch_id, branch_head_id, [], []))
    review_rebases.append(rebase_id)

    rebases[rebase_id] = {
        "review_id": review_id,
        "updater_id": updater_id,
        "old_head_id": old_head_id,
        "new_head_id": new_head_id,
        "old_upstream_id": old_upstream_id,
        "new_upstream_id": new_upstream_id,
        "equivalent_merge_id": equivalent_merge_id,
        "replayed_rebase_id": replayed_rebase_id,
        "previousreachable": set()
    }

cursor.execute("""SELECT rebase, ARRAY_AGG(commit)
                    FROM previousreachable
                GROUP BY rebase""")

for rebase_id, commit_ids in cursor:
    rebases[rebase_id]["previousreachable"] = set(commit_ids)

for review_id, (branch_id, branch_head_id,
                rebase_ids, branchupdates) in reviews.items():
    cursor.execute("""SELECT commit
                        FROM branchcommits
                       WHERE branch=%s""",
                   (branch_id,))

    commit_ids = set(commit_id for commit_id, in cursor)

    def add_update(rebase_id, updater_id,
                   old_head_id, new_head_id,
                   old_upstream_id, new_upstream_id,
                   added_commit_ids, removed_commit_ids,
                   extra_commit_id=None):
        cursor.execute(
            """INSERT
                 INTO branchupdates (branch, updater,
                                     from_head, to_head,
                                     from_tail, to_tail)
               VALUES (%s, %s,
                       %s, %s,
                       %s, %s)
            RETURNING id""",
            (branch_id, updater_id,
             old_head_id, new_head_id,
             old_upstream_id, new_upstream_id))
        update_id, = cursor.fetchone()
        cursor.execute(
            """INSERT
                 INTO reviewupdates (branchupdate, review)
               VALUES (%s, %s)""",
            (update_id, review_id))
        cursor.executemany(
            """INSERT
                 INTO branchupdatecommits (branchupdate, commit, associated)
               VALUES (%s, %s, TRUE)""",
            ((update_id, commit_id)
             for commit_id in added_commit_ids))
        cursor.executemany(
            """INSERT
                 INTO branchupdatecommits (branchupdate, commit, associated)
               VALUES (%s, %s, FALSE)""",
            ((update_id, commit_id)
             for commit_id in removed_commit_ids))
        if extra_commit_id:
            added_commit_ids.add(extra_commit_id)
        commit_ids = list(added_commit_ids)
        cursor.execute(
            """UPDATE reviewchangesets
                  SET branchupdate=%s
                WHERE review=%s
                  AND branchupdate IS NULL
                  AND changeset IN (SELECT id
                                      FROM changesets
                                     WHERE child=ANY (%s)
                                        OR parent=ANY (%s))""",
            (update_id, review_id, commit_ids, commit_ids))
        if rebase_id:
            cursor.execute(
                """UPDATE reviewrebases
                      SET branchupdate=%s
                    WHERE id=%s""",
                (update_id, rebase_id))

    def get_parents(commit_id):
        cursor = dbschema.db.cursor()
        cursor.execute("""SELECT parent
                            FROM edges
                           WHERE child=%s""",
                       (commit_id,))
        for (parent_id,) in cursor:
            if parent_id in commit_ids:
                yield parent_id

    def collect_tree(root_id):
        pending = set([root_id])
        processed = set()
        while pending:
            commit_id = pending.pop()
            processed.add(commit_id)
            parents = list(get_parents(commit_id))
            yield commit_id
            pending.update(parent_id
                           for parent_id in parents
                           if parent_id not in processed)

    rebase_ids.sort(reverse=True)
    for rebase_id in rebase_ids:
        rebase = rebases[rebase_id]

        if rebase["new_head_id"] != branch_head_id:
            rebased_commits = set(collect_tree(rebase["new_head_id"]))
            added_commit_ids = commit_ids - rebased_commits
            add_update(
                None, None,
                rebase["new_head_id"], branch_head_id,
                rebase["new_upstream_id"], rebase["new_upstream_id"],
                added_commit_ids, [])
            commit_ids = rebased_commits

        added_commit_ids = commit_ids - rebase["previousreachable"]
        removed_commit_ids = rebase["previousreachable"] - commit_ids

        add_update(
            rebase_id, rebase["updater_id"],
            rebase["old_head_id"], rebase["new_head_id"],
            rebase["old_upstream_id"], rebase["new_upstream_id"],
            added_commit_ids, removed_commit_ids,
            rebase["equivalent_merge_id"] or rebase["replayed_rebase_id"])

        commit_ids = rebase["previousreachable"]
        branch_head_id = rebase["old_head_id"]

    add_update(
        None, None,
        None, rebase["old_head_id"],
        None, rebase["old_upstream_id"],
        commit_ids, [])

cursor.execute(
    """CREATE UNIQUE INDEX reviewrebases_review
                        ON reviewrebases (review)
                     WHERE branchupdate IS NULL""")

cursor.execute(
    """UPDATE commentchains
          SET addressed_by_update=branchupdates.id
         FROM reviews, branchupdates, branchupdatecommits
        WHERE commentchains.review=reviews.id
          AND reviews.branch=branchupdates.branch
          AND branchupdates.id=branchupdatecommits.branchupdate
          AND branchupdatecommits.commit=commentchains.addressed_by
          AND branchupdatecommits.associated""")

dbschema.db.commit()

try:
    # This would fail if we didn't manage to map all review changesets to a
    # review update. Shouldn't happen, but doesn't seem all too unlikely,
    # especially not in an "older" system.
    cursor.execute(
        """ALTER TABLE reviewchangesets
           ALTER COLUMN branchupdate SET NOT NULL""")
except Exception:
    print(("WARNING: Failed to add NOT NULL to "
                         "|reviewchangesets.branchupdate| column."), file=sys.stderr)
    dbschema.db.rollback()

# Since |reviewrebases| now references |branchupdates|, which has |from_head|
# and |to_head| columns, |old_head| and |new_head| are redundant.
cursor.execute(
    """ALTER TABLE reviewrebases
         DROP COLUMN old_head,
         DROP COLUMN new_head""")

cursor.execute("DROP TABLE reachable")
cursor.execute("DROP TABLE previousreachable")

dbschema.db.commit()
