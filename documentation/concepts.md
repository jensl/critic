Critic(al) Concepts
===================

Branches
--------

Critic maintains a view of branches that is slightly different from git's.  In
addition to knowing the head of the branch, that is, the most recent commit, it
also keeps track of (after basically inventing the information itself) a base
branch and a "tail" commit.  A branch is considered to "contain" all commits
that are reachable from its head commit, except all commits that are reachable
from the base branch.

This view of a branch is useful when the purpose is (possibly) to review the
work done on the branch.  In this case, one needs to limit the scope to where
the branch started, since in git's view, the branch contains everything back to
the beginning of time, which is not what one means to review.

It's important to note, however, that the "base" of a branch is not something
that is stored in git, and thus Critic needs to resort to fairly simple
heuristics in determining the base of a branch, and can get it wrong.  In
particular, it will reverse the relationship between related branches in some
cases.  If a branch A is created from master, and then later a branch B is
created from branch A, and branches A and B diverge, the "correct" relationships
are that A's base branch is master and B's base branch is A.  However, if B is
pushed to Critic's repository before A, Critic's will think that B's base branch
is master and A's base branch is B.  If branches are pushed to Critic's
repository in the order which they are created, then Critic will get it right,
though.

Reviews
-------

A review in Critic is a branch in Critic's repository, and the changes to be
reviewed are the commits (that, according to Critic, are) contained on that
branch.  There are two basic ways to start a review: push a branch to Critic's
repository and create a review of all the changes on the branch, or select one
or more commits and have Critic create a branch containing exactly those
commits.  In practice, the difference between the two alternatives is quite
insignificant.

The branch is like any other git branch.  It can be fetched from Critic's
repository into a local work repository, and additional commits can be pushed
back to Critic's repository.  Commits pushed to Critic's repository are
automatically added to the review, as changes that need reviewing.

At this time, non-fast forward updates of review branches in Critic's repository
are not possible.

Reviewers
---------

Reviewers are users of Critic that have registered themselves as reviewers of
parts of the source code tree.  When changes are scheduled for review, reviewers
are automatically assigned, based on this configuration.  Thus the user
requesting the review needn't assign reviewers manually.

Chunks
------

Each commit scheduled to be reviewed as part of a review is split into
individual change "chunks" (N lines deleted, M lines added,) individually
recorded in Critic's database along with a status.  Each such chunk of changes
needs to be approved by a registered reviewer for the modified file.  The
low-level details is typically hidden from the reviewers, however.  They don't
need to explicitly approve each chunk individually, for instance.

"Approval" of chunks of changes is not thought to be final, and thus not
standing in conflict with not accepting the changes as-is.  (And thus the term
"approve" is slightly misleading; "read" or "reviewed" would be perhaps more
appropriate.)

Any chunk of changes not approved yet blocks the review from being "accepted".

Comments
--------

A vital part of reviewing is commenting specific lines of code.  In Critic,
there are two types of comments; "issues" and "notes".  An "issue" is a comment
that must be addressed, one way or another, before the review can be "accepted."
A "note" is simply a note; it has no formal significance.

When a new version of the file that is commented is created (by adding
additional commits to the review,) one of two things may happen to existing
comments: they can be transferred to the new version, if all commented lines are
identical in the new version of the file, or marked as "addressed," if any
commented line was modified.  When a comment is automatically marked as
"addressed," it could be because it was in fact properly addressed, or it could
be because some unrelated change was made to the commented lines.  In the latter
case, the author of the comment (or anyone else, for that matter) may "reopen"
the comment by manually transferring the comment to a sequence of lines in the
new version of the file.

It may seem as if "issue" comments might easily be "lost" by unrelated changes
touching the commented lines, but everyone involved in the comment (its author
and anyone who replied to it) will be notified that the comment was marked as
addressed, and of course, the new changes in the file have to be reviewed as any
other changes; the fact that they "addressed" a comment does not automatically
mark the changes themselves as approved.

"Issue" comments can also be explicitly closed their authors (or reviewers of
the file in which the comment was made) after discussion, if the agreement is
that no changes to the commented code needs to be made.

Review Progress
---------------

The ultimate goal of a review is to close it.  A review can only be closed when
it is in an "accepted" state, which, in turn, it is when each and every chunk of
changes have been approved by reviewers, and every "issue" comment has been
marked either as addressed or closed.

Reviews can also be dropped, meaning the changes are not meant to be merged in
their current change.  To drop a currently accepted (but not closed) review,
you need to create an issue to "un-accept" it.  It is suitable to explain
why the review will be dropped in that issue.
