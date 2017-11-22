# Reviewable and non-reviewable commits

In short, a review in Critic can be said to consist of both reviewable and (in
some cases) non-reviewable commits. This can be somewhat confusing.

## The basics

In Critic, the "is reviewed" status of changes is tracked per file and commit.
In practice, this means that for every file modified in each commit pushed to
the review branch in Critic's repository, a "flag" is created that needs to be
set by a reviewer in order for the review to be accepted. Those flags can be set
for instance when looking at the diff of a single one of those commits.

Commits for which such flags were created are hereby called "reviewable."

## Rebases

Critic also supports rebasing review branches, either to rewrite/clean up the
commit history, or to move/transplant the changes onto a different upstream
commit. From Critic's perspective, a rebase effectively replaces all or some of
the original commits with new commits.

Usually, these new commits will logically represent the same overall work, but
since invididual changes could have been moved between commits, or many commits
been squashed into one, or one been split into many, it's difficult to establish
an unambiguous mapping between the new commits and the per-commit-and-file flags
discussed above.

Consequently, all commits on the post-rebase version of the review branch that
were not present on the pre-rebase version are "non-reviewable." They exist in
Critic's repository and their diffs can of course be displayed in Critic's UI.
However, since there are no flags associated with them, when dispaying their
diffs, there will be no toggles to mark the changes as reviewed.

## The `All changes` diff

In the `Actions` menu in the top-right corner of the review log, there's an
option (Display diff of ...) `All changes`. This always displays a diff between
the current tip of the review branch and its upstream commit. If the reviewed
changes has been rebased onto a new upstream commit, this diff will technically
not be of the reviewable commits, but it will obviously contain all changes to
be reviewed. Consequently, this diff will always have toggles to mark all
changes in the review as reviewed.
