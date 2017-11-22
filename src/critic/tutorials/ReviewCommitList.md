# Reviewing changes

The reviewing of changes in Critic is centered around the commits on the review
branch. Displaying the diff of a commit is thus the most basic way of performing
the reviewing. Critic does offer a variety of ways to display and review
changes, however.

## Selecting a single commit

To display the diff of a single commit, click anywhere on the commit's line in
the list of commits. A "popup" shows up with a "Review 1 commit" button.
Clicking this button displays the diff of the selected commit. Or, instead of
clicking the button, press the `ENTER` key.

## Selecting a range of commits

When a review branch consists of multiple commits, it may be useful to display a
combined diff of two or more of those commits. This can be accomplished in a few
different ways:

* Click the first commit in the desired range and then click the last commit.
* Select a range like when selecting text: press the mouse button over the first
  commit in the range, move the pointer to the last commit in the range, and
  then release the mouse button.
* Select a commit using the `UP`/`DOWN` arrow keys and then expand the selection
  using the `UP`/`DOWN` arrow keys while holding down the `SHIFT` key.

In all cases, the same "popup" as in the single commit case shows up, with the
button now saying "Review N commits". Clicking the button, or pressing the
`ENTER` key, displays the combined diff of the selected commits.

### Unsupported commit ranges

Some ranges of commits in the commit list cannot be combined as a single diff.
This includes some cases when one or more merge commits are included, and any
case when the range includes a point where the review branch was rebased. You
will know that a range is unsupported because it will be impossible to select
it.

Note that even when it is not possible to display a diff of all changes in a
review by selecting all commits in the log (because of rebases or merges being
"in the way"), it is almost always possible to display such a diff using the
`Show diff of ...` / `Everything` option in the `Actions` menu in the top-right
corner of the review commit log.
