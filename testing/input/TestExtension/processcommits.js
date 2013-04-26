/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function processcommits(review, changeset, commitset) {
  writeln("r/%d", review.id);
  writeln("%s..%s", changeset.parent.sha1.substring(0, 8), changeset.child.sha1.substring(0, 8));
  writeln("%s", commitset.map(function (commit) { return commit.sha1.substring(0, 8); }));
}
