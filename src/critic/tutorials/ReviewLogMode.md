# Review log modes

The "review log", i.e. the list of commits displayed on the main page of a
review, has three different modes. The mode can be selected in the `Actions`
menu in the top-right corner of the review commit log.

## Reviewable commits

In this mode, which is the default, the commit log displays all reviewable
commits. If the review branch has been rebased along the way, the [reviewable
commits][reviewablecommits] will effectively come from different versions of the
review branch, and thus not represent a connected graph. But a reviewer can
always display the diff of any one of the commits and from that diff mark
changes as reviewed.

The list of commits is interspersed with markers showing how the branch has been
rebased.

## Actual branch log

In this mode, the commit log simply displays a regular log of the current
version of the review branch, in topological order. Commits pushed to the branch
since the most recent rebase will be reviewable, while rebased commits will not.
When diffs of the latter category of commits are displayed, it will not be
possible to mark the changes as reviewed, since Critic can't definitively know
which flags this should set.

## Smart mode

In this mode, the log is switched from "reviewable commits" to "actual branch
log" at the most recent rebase point where it can be done without hiding any
reviewable commits that are not 100 % marked as reviewed. In other words, if
none of the changes in the review have been marked as reviewed, this mode will
be the same as the "reviewable commits" mode, and if all of the changes have
been marked as reviewed, it will be same as the "actual branch log" mode.

This makes sure unreviewed follow-up commits are always displayed, even if the
branch has already been rebased after they were added, but still displays a
cleaned-up log of older and already reviewed work.

[reviewablecommits]: #tutorial:ReviewableCommits.md
