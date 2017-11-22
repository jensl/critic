/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2013 Jens Lindström, Opera Software ASA

 Licensed under the Apache License, Version 2.0 (the "License"); you may not
 use this file except in compliance with the License.  You may obtain a copy of
 the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 License for the specific language governing permissions and limitations under
 the License.

*/

"use strict";

function CriticComment(chain_id, batch_id, comment_id, user_id, time, state, text, data)
{
  this.id = comment_id;
  this.user = new CriticUser(user_id);
  this.time = time;
  this.text = text;

  var self = this;
  var chain = data.chain || null;
  var batch = data.batch || null;

  function getChain()
  {
    if (!chain)
      chain = new CriticCommentChain(chain_id, { comments: { comment_id: self }});
    return chain;
  }

  function getBatch()
  {
    if (!batch)
      batch = new CriticBatch(batch_id);
    return batch;
  }

  Object.defineProperties(this, { chain: { get: getChain, enumerable: true },
                                  batch: { get: getBatch, enumerable: true }});
  Object.freeze(this);
}

function CriticCommentChain(result_or_chain_id, data)
{
  var chain_id, result;

  if (typeof result_or_chain_id == "number")
  {
    chain_id = result_or_chain_id;
    result = db.execute("SELECT id, review, batch, uid, time, type, state, origin, file, first_commit, last_commit, closed_by, addressed_by FROM commentchains WHERE id=%d", chain_id)[0];
  }
  else
  {
    result = result_or_chain_id;
    chain_id = result.id;
  }

  if (!result)
    throw CriticError(format("%d: invalid comment chain ID", chain_id));

  data = data || {};

  this.id = chain_id;
  this.type = result.type == "issue" ? CriticCommentChain.TYPE_ISSUE : CriticCommentChain.TYPE_NOTE;

  switch (result.state)
  {
  case "open":
    this.state = CriticCommentChain.STATE_OPEN;
    break;

  case "closed":
    this.state = CriticCommentChain.STATE_RESOLVED;
    break;

  case "addressed":
    this.state = CriticCommentChain.STATE_ADDRESSED;
    break;
  }

  var self = this;
  var review_id = result.review, review = data.review || null;
  var batch_id = result.batch, batch = data.batch || null;
  var user_id = result.uid, user = data.user || null;
  var users = null;
  var closed_by_id = result.closed_by, closed_by = null;
  var file_id, file;
  var commit_id, first_commit_id, last_commit_id, addressed_by_id;
  var changeset, addressed_by, commit, lines, context;
  var comments;

  function getReview()
  {
    if (!review)
      review = new CriticReview(review_id);
    return review;
  }

  function getBatch()
  {
    if (!batch)
      batch = new CriticBatch(batch_id);
    return batch;
  }

  function getUser()
  {
    if (!user)
      user = new CriticUser(user_id);
    return user;
  }

  function getUsers()
  {
    if (!users)
    {
      users = {};

      var result = db.execute("SELECT uid FROM commentchainusers WHERE chain=%d", self.id);

      for (var index = 0; index < result.length; ++index)
        users[result[index].uid] = new CriticUser(result[index].uid);

      Object.freeze(users);
    }

    return users;
  }

  function getClosedBy()
  {
    if (!closed_by)
      if (!closed_by_id)
        return null;
      else
        closed_by = new CriticUser(closed_by_id);

    return closed_by;
  }

  function getChangeset()
  {
    if (changeset === void 0)
      if (first_commit_id === last_commit_id)
        changeset = null;
      else
      {
        var review = getReview();
        var first_commit = review.repository.getCommit(first_commit_id);
        var last_commit = review.repository.getCommit(last_commit_id);

        changeset = new CriticChangeset(review.repository, { parent: first_commit, child: last_commit, files: [file_id] });
      }

    return changeset;
  }

  function getAddressedBy()
  {
    if (!addressed_by)
      if (!addressed_by_id)
        return null;
      else
      {
        var review = getReview();
        addressed_by = review.repository.getCommit(addressed_by_id);
      }

    return addressed_by;
  }

  function getCommit()
  {
    if (!commit)
    {
      var review = getReview();
      commit = review.repository.getCommit(commit_id);
    }

    return commit;
  }

  function getFile()
  {
    if (!file)
      if (self.changeset)
        file = self.changeset.files[0];
      else
        file = review.repository.getCommit(first_commit_id).getFile(file_id);

    return file;
  }

  function getLines()
  {
    if (!lines)
    {
      lines = {};

      var result = db.execute("SELECT sha1, first_line, last_line FROM commentchainlines WHERE chain=%d AND state='current'", chain_id);

      for (var index = 0; index < result.length; ++index)
      {
        var row = result[index];
        lines[row.sha1] = Object.freeze({ firstLine: row.first_line - 1, lastLine: row.last_line - 1 });
      }

      Object.freeze(lines);
    }

    return lines;
  }

  function getContext(minimized)
  {
    if (context === void 0)
    {
      var version;

      if (self.file instanceof CriticFileVersion)
        version = self.file;
      else if (self.origin == "old")
        version = self.file.oldVersion;
      else
        version = self.file.newVersion;

      var position = self.lines[version.sha1];
      var result = db.execute("SELECT context FROM codecontexts WHERE sha1=%s AND first_line<=%d AND last_line>=%d ORDER BY first_line DESC LIMIT 1", version.sha1, position.firstLine + 1, position.lastLine + 1)[0];

      if (result)
        context = result.context;
      else
        context = null;
    }

    if (minimized && context)
      return context.replace(/\(.*(?:\)|...$)/, "(...)");
    else
      return context;
  }

  function getComments()
  {
    if (!comments)
    {
      comments = [];

      var result = db.execute("SELECT id, batch, uid, time, state, comment FROM comments WHERE chain=%d AND state='current' ORDER BY time ASC", chain_id);

      for (var index = 0; index < result.length; ++index)
      {
        var row = result[index];
        comments.push(data.comments && data.comments[row.id] || new CriticComment(chain_id, row.batch, row.id, row.uid, row.time, row.state, row.comment, { chain: self }));
      }

      Object.freeze(comments);
    }

    return comments;
  }

  if (result.file)
  {
    this.origin = result.origin;

    file_id = result.file;
    file = data.file || null;

    first_commit_id = result.first_commit;
    last_commit_id = result.last_commit;
    addressed_by_id = result.addressed_by;

    Object.defineProperties(this, { changeset: { get: getChangeset, enumerable: true },
                                    addressedBy: { get: getAddressedBy, enumerable: true },
                                    file: { get: getFile, enumerable: true },
                                    lines: { get: getLines, enumerable: true },
                                    context: { get: getContext, enumerable: true },
                                    minimizedContext: { get: function () { return getContext(true); }, enumerable: true }});
  }
  else if (result.first_commit && result.last_commit)
  {
    commit_id = result.first_commit;

    var result2 = db.execute("SELECT first_line, last_line FROM commentchainlines WHERE chain=%d", chain_id)[0];

    this.firstLine = result2.first_line;
    this.lastLine = result2.last_line;

    result2 = null;

    Object.defineProperty(this, "commit", { get: getCommit, enumerable: true });
  }

  result = null;

  Object.defineProperties(this, { review: { get: getReview, enumerable: true },
                                  batch: { get: getBatch, enumerable: true },
                                  user: { get: getUser, enumerable: true },
                                  users: { get: getUsers, enumerable: true },
                                  closedBy: { get: getClosedBy, enumerable: true },
                                  comments: { get: getComments, enumerable: true }});
  Object.freeze(this);
}

Object.defineProperties(CriticCommentChain, { TYPE_ISSUE:      { value: 0 },
                                              TYPE_NOTE:       { value: 1 },
                                              STATE_OPEN:      { value: 0 },
                                              STATE_RESOLVED:  { value: 1 },
                                              STATE_ADDRESSED: { value: 2 }});

CriticCommentChain.find = function (data)
  {
    var commit;
    if (typeof data.commit == "object" && data.commit instanceof CriticCommit)
      commit = data.commit;
    else
    {
      var repository = data.repository;
      if (!repository || !(repository instanceof CriticRepository))
        throw CriticError("invalid argument; data.commit must be a Commit object, or data.repository must be a Repository object");
      commit = repository.getCommit(data.commit);
    }

    var review = null;
    if ("review" in data)
    {
      if (typeof data.review == "object" && data.review instanceof CriticReview)
        review = data.review;
      else
        review = new CriticReview(data.review);
    }

    var result = [];

    if ("file" in data)
    {
      var file;
      if (typeof data.file == "object" && data.file instanceof CriticFile)
        file = data.file;
      else
        file = CriticFile.find(data.file);

      var fileversion = commit.getFile(file.path);
      var args = ["SELECT DISTINCT commentchains.review, commentchainlines.chain, commentchainlines.first_line, commentchainlines.last_line " +
                  "  FROM commentchains " +
                  "  JOIN commentchainlines ON (commentchainlines.chain=commentchains.id) " +
                  " WHERE commentchainlines.sha1=%s " +
                  "   AND commentchains.state IN ('open', 'closed', 'addressed')",
                  fileversion.sha1];

      if (review !== null)
      {
        args[0] += " AND commentchains.review=%d";
        args.push(review.id);
      }

      result = db.execute.apply(db, args);
    }
    else if (review)
    {
      var preliminary = db.execute("SELECT DISTINCT commentchains.id, commentchains.file, commentchainlines.sha1, " +
                                   "                commentchainlines.first_line, commentchainlines.last_line " +
                                   "  FROM commentchains " +
                                   "  JOIN commentchainlines ON (commentchainlines.chain=commentchains.id) " +
                                   " WHERE commentchains.review=%d " +
                                   "   AND commentchains.state IN ('open', 'closed', 'addressed')",
                                   review.id);

      var files_in_commit = {};

      preliminary.apply(
        function (chain_id, file_id, sha1, first_line, last_line)
        {
          if (!(file_id in files_in_commit))
            try
            {
              files_in_commit[file_id] = commit.getFile(CriticFile.find(file_id).path).sha1;
            }
            catch (error)
            {
              files_in_commit[file_id] = "";
            }

          if (sha1 == files_in_commit[file_id])
            result.push({ review: review.id,
                          chain: chain_id,
                          first_line: first_line,
                          last_line: last_line });
        });
    }

    var chains = [];
    var reviews = {};

    for (var index = 0; index < result.length; ++index)
    {
      var review_id = result[index].review;
      var review = reviews[review_id] || (reviews[review_id] = new CriticReview(review_id));

      chains.push({ chain: new CriticCommentChain(result[index].chain, { review: review }),
                    lineIndex: result[index].first_line - 1,
                    lineCount: result[index].last_line - result[index].first_line + 1 });
    }

    return chains;
  };

CriticCommentChain.prototype.getComment = function (id)
  {
    id = ~~id;

    var result = db.execute("SELECT batch, uid, time, state, comment FROM comments WHERE chain=%d AND id=%d AND state='current'", this.id, id)[0];
    return new CriticComment(this.id, result.batch, id, result.uid, result.time, result.state, result.comment, { chain: this });
  };
