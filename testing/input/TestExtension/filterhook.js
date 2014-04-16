/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function filterhook(data, review, user, commits, files) {
  files.forEach(
    function (file) {
      if (file.path == "015-filterhook/include/explode")
        throw Error("Boom!");
    });

  var transaction = new critic.MailTransaction;

  transaction.add({
    to: critic.User.current,
    subject: "filterhook.js::filterhook()",
    review: review,
    body: format("data: %r\n" +
                 "review.id: %d\n" +
                 "user.name: %s\n" +
                 "commits: %r\n" +
                 "files: %r\n",
                 data,
                 review.id,
                 user.name,
                 commits.map(function (commit) { return commit.message; }),
                 files.map(function (file) { return file.path; }).sort())
  });

  transaction.finish();
}
