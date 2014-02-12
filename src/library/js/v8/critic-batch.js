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

var batch_internals = {};
var batch_id_counter = 0;

function CriticBatch(data)
{
  var self = this;
  var review_id, review;
  var user_id, user;
  var chain_id, chain;
  var issues;
  var notes;
  var replies;

  var internal_id = batch_id_counter++;
  var internals = batch_internals[internal_id] = {};

  Object.defineProperty(this, "__id__", { value: internal_id });

  function getReview()
  {
    if (!review)
      review = new CriticReview(review_id);
    return review;
  }

  function getUser()
  {
    if (!user)
      user = new CriticUser(user_id);
    return user;
  }

  function getCommentChain()
  {
    if (chain === void 0)
    {
      if (chain_id === null)
        chain = null;
      else
        chain = new CriticCommentChain(chain_id, { batch: self, review: review });
    }
    return chain;
  }

  function getIssues()
  {
    if (!issues)
    {
      issues = [];

      var result = db.execute(("SELECT id, review, batch, uid, time, type, state, origin, file, " +
                                      "first_commit, last_commit, closed_by, addressed_by " +
                                 "FROM commentchains " +
                                "WHERE batch=%d " +
                                  "AND type='issue' " +
                                "ORDER BY time ASC"), self.id);

      for (var index = 0; index < result.length; ++index)
        issues.push(new CriticCommentChain(result[index], { batch: self }));

      Object.freeze(issues);
    }

    return issues;
  }

  function getNotes()
  {
    if (!notes)
    {
      notes = [];

      var result = db.execute(("SELECT id, review, batch, uid, time, type, state, origin, file, " +
                                      "first_commit, last_commit, closed_by, addressed_by " +
                                 "FROM commentchains " +
                                "WHERE batch=%d " +
                                  "AND type='note' " +
                                "ORDER BY time ASC"), self.id);

      for (var index = 0; index < result.length; ++index)
        notes.push(new CriticCommentChain(result[index], { batch: self }));

      Object.freeze(notes);
    }

    return notes;
  }

  function getReplies()
  {
    if (!replies)
    {
      replies = [];

      var result = db.execute(("SELECT id, chain, uid, time, state, comment " +
                                 "FROM comments " +
                                "WHERE batch=%d"), self.id);

      for (var index = 0; index < result.length; ++index)
      {
        var row = result[index];
        replies.push(new CriticComment(row.chain, self.id, row.id, row.uid, row.time, row.state, row.comment, { batch: self }));
      }

      Object.freeze(replies);
    }

    return replies;
  }

  if (typeof data.id == "number")
  {
    this.id = data.id;

    var result = db.execute("SELECT review, uid, comment, time FROM batches WHERE id=%d", this.id)[0];

    if (!result)
      throw CriticError(format("%d: invalid batch ID", this.id));

    this.time = result.time;

    review_id = result.review;
    review = data.review || null;
    user_id = result.uid;
    user = data.user || null;
    chain_id = result.comment;
    chain = data.comment || null;

    Object.defineProperties(this, { review: { get: getReview, enumerable: true },
                                    user: { get: getUser, enumerable: true },
                                    commentChain: { get: getCommentChain, enumerable: true },
                                    issues: { get: getIssues, enumerable: true },
                                    notes: { get: getNotes, enumerable: true },
                                    replies: { get: getReplies, enumerable: true }});
  }
  else if (data.internals === batch_internals)
  {
    this.id = null;
    this.review = data.review;
    this.user = data.user;

    internals.filter_user_ids = {};
    internals.filter_operations = [];
    internals.comment_operations = [];
    internals.assignments = { fileCount: 0 };
    internals.added_filters = [];
    internals.removed_filters = [];

    internals.replied_to_chains = {};
    internals.modified_issues = {};

    internals.review_created = data.review_created;
  }
  else
    throw CriticError("invalid argument");

  Object.freeze(this);
}

function commitFromFileVersion(file_version)
{
  if (file_version instanceof CriticChangesetFileVersion)
    if (file_version == file_version.file.oldVersion)
      return file_version.file.changeset.parent;
    else
      return file_version.file.changeset.child;
  else
    return file_version.commit;
}

function propagateCommentChain(review, start, line_index, line_count, forward, chain)
{
  var lines = [];
  var commits = review.commits;
  var path = start.path;
  var commit = commitFromFileVersion(start);

  if (!forward && !(commit.sha1 in commits.parents))
    return [lines, "clean"];

  while (true)
  {
    var next;

    if (forward)
      if (commits.children[commit.sha1].length > 1)
        return [lines, "merge", commit];
      else
        next = commits.children[commit.sha1][0];
    else
      if (commit.parents.length != 1)
        return [lines, "merge", commit];
      else
        next = commits.parents[commit.sha1][0];

    if (!next)
      return [lines, "clean"];

    var parent, child;

    if (forward)
    {
      parent = commit;
      child = next;
    }
    else
    {
      parent = next;
      child = commit;
    }

    var changeset = review.repository.getChangeset({ parent: parent, child: child });
    var file = changeset.files[path];

    if (file)
    {
      var next_version = forward ? file.newVersion : file.oldVersion;

      if (!next_version)
        if (forward)
          /* File was removed. */
          return [lines, "modified", next];
        else
          /* File was added. */
          return [lines, "clean"];

      var delta = 0, sha1 = next_version.sha1;

      if (chain && !forward && sha1 in chain.lines)
        return [lines, "clean"];

      for (var index = 0; index < file.chunks.length; ++index)
      {
        var chunk = file.chunks[index], chunk_start, chunk_end, chunk_delta;

        if (forward)
        {
          chunk_start = chunk.deleteOffset;
          chunk_end = chunk.deleteOffset + chunk.deleteCount;
          chunk_delta = chunk.insertCount - chunk.deleteCount;
        }
        else
        {
          chunk_start = chunk.insertOffset;
          chunk_end = chunk.insertOffset + chunk.insertCount;
          chunk_delta = chunk.deleteCount - chunk.insertCount;
        }

        if (chunk_end <= line_index)
          delta += chunk_delta;
        else if (chunk_start <= line_index + line_count)
          return [lines, "modified", next];
        else
          break;
      }

      line_index += delta;

      lines.push([next, sha1, line_index, line_count]);
    }

    commit = next;
  }
}

function createCommentChain(text, data, type)
{
  data = data || {};
  text = text && String(text);

  if (!(this instanceof CriticBatch))
    throw CriticError("invalid this object; expected batch object");
  if (!text)
    throw CriticError("invalid use: can't add empty comment");

  var users = {};

  function addUser(user)
  {
    users[user.id] = user;
  }

  function insertUsers(chain_id, comment_id)
  {
    for (var user_id in users)
    {
      db.execute("INSERT INTO commentchainusers (chain, uid) VALUES (%d, %d)", chain_id, user_id);
      db.execute("INSERT INTO commentstoread (uid, comment) VALUES (%d, %d)", user_id, comment_id);
    }
  }

  addUser(this.user);

  this.review.owners.forEach(addUser);

  var operations = batch_internals[this.__id__].comment_operations;

  if (data.fileVersion)
  {
    if (!(data.fileVersion instanceof CriticFileVersion))
      throw CriticError("data.fileVersion: invalid argument; expected file version object");
    if (typeof data.lineIndex != "number")
      throw CriticError("data.lineIndex: invalid argument; expected number");
    if (typeof data.lineCount != "number")
      throw CriticError("data.lineCount: invalid argument; expected number");

    var file_version = data.fileVersion;
    var propagation_back = propagateCommentChain(this.review, file_version, data.lineIndex, data.lineCount, false);
    var propagation_forward = propagateCommentChain(this.review, file_version, data.lineIndex, data.lineCount, true);
    var state = 'open';
    var addressed_by = null;

    if (type == "issue")
      switch (propagation_forward[1])
      {
      case "clean":
        break;
      case "merge":
        throw CriticError(format("cannot raise issue; commit is followed by a merge commit: %s", propagation_forward[2].sha1));
      case "modified":
        if (data.allowInitiallyAddressed)
        {
          state = 'addressed';
          addressed_by = propagation_forward[2];
        }
        else
          throw CriticError(format("cannot raise issue; lines are modified by a later commit: %s", propagation_forward[2].sha1));
      }

    var sha1s = {};
    var lines = [[commitFromFileVersion(file_version), file_version.sha1, data.lineIndex, data.lineCount]]
                  .concat(propagation_back[0], propagation_forward[0])
                  .filter(function (data) { if (data[1] in sha1s) return false; sha1s[data[1]] = true; return true; });
    var origin, parent, child;

    if (file_version instanceof CriticChangesetFileVersion)
    {
      origin = file_version == file_version.file.oldVersion ? "old" : "new";
      parent = file_version.file.changeset.parent;
      child = file_version.file.changeset.child;
    }
    else
    {
      origin = "new";
      parent = child = file_version.commit;
    }

    operations.push(function (batch_id)
      {
        var chain_id = db.execute("INSERT INTO commentchains (review, batch, uid, type, state, origin, file, first_commit, last_commit) VALUES (%d, %d, %d, %s, %s, %s, %d, %d, %d) RETURNING id",
                                  this.review.id, batch_id, this.user.id, type, state, origin, file_version.id, parent.id, child.id)[0].id;

        if (addressed_by)
          db.execute("UPDATE commentchains SET addressed_by=%d WHERE id=%d", addressed_by.id, chain_id);

        var comment_id = db.execute("INSERT INTO comments (chain, batch, uid, state, comment) VALUES (%d, %d, %d, 'current', %s) RETURNING id",
                                    chain_id, batch_id, this.user.id, text)[0].id;

        db.execute("UPDATE commentchains SET first_comment=%d WHERE id=%d", comment_id, chain_id);

        for (var index = 0; index < lines.length; ++index)
        {
          var line = lines[index];

          db.execute("INSERT INTO commentchainlines (chain, uid, state, commit, sha1, first_line, last_line) VALUES (%d, %d, 'current', %d, %s, %d, %d)",
                     chain_id, this.user.id, line[0].id, line[1], line[2] + 1, line[2] + line[3]);
        }

        insertUsers(chain_id, comment_id);
      });
  }
  else if (data.commit)
  {
    if (typeof data.lineIndex != "number")
      throw CriticError("data.lineIndex: invalid argument; expected number");
    if (typeof data.lineCount != "number")
      throw CriticError("data.lineCount: invalid argument; expected number");

    var lines = data.commit.message.trim().split("\n");

    if (data.lineIndex >= lines.length || data.lineIndex + data.lineCount > lines.length || data.lineCount == 0)
      throw CriticError("data.lineIndex/data.lineCount: out of range or invalid");

    operations.push(function (batch_id)
      {
        var chain_id = db.execute("INSERT INTO commentchains (review, batch, uid, type, state, first_commit, last_commit) VALUES (%d, %d, %d, %s, 'open', %d, %d) RETURNING id",
                                  this.review.id, batch_id, this.user.id, type, data.commit.id, data.commit.id)[0].id;

        var comment_id = db.execute("INSERT INTO comments (chain, batch, uid, state, comment) VALUES (%d, %d, %d, 'current', %s) RETURNING id",
                                    chain_id, batch_id, this.user.id, text)[0].id;

        db.execute("UPDATE commentchains SET first_comment=%d WHERE id=%d", comment_id, chain_id);

        db.execute("INSERT INTO commentchainlines (chain, uid, state, commit, sha1, first_line, last_line) VALUES (%d, %d, 'current', %d, %s, %d, %d)",
                   chain_id, this.user.id, data.commit.id, data.commit.sha1, data.lineIndex, data.lineIndex + data.lineCount - 1);

        insertUsers(chain_id, comment_id);
      });
  }
  else
    operations.push(function (batch_id)
      {
        var chain_id = db.execute("INSERT INTO commentchains (review, batch, uid, type, state) VALUES (%d, %d, %d, %s, 'open') RETURNING id",
                                  this.review.id, batch_id, this.user.id, type)[0].id;

        var comment_id = db.execute("INSERT INTO comments (chain, batch, uid, state, comment) VALUES (%d, %d, %d, 'current', %s) RETURNING id",
                                    chain_id, batch_id, this.user.id, text)[0].id;

        db.execute("UPDATE commentchains SET first_comment=%d WHERE id=%d", comment_id, chain_id);

        insertUsers(chain_id, comment_id);
      });
}

CriticBatch.prototype.raiseIssue = function (text, data) { createCommentChain.call(this, text, data, "issue"); };
CriticBatch.prototype.writeNote = function (text, data) { createCommentChain.call(this, text, data, "note"); };

CriticBatch.prototype.addReply = function (chain, text)
  {
    var internals = batch_internals[this.__id__];
    var operations = internals.comment_operations;

    text = text && String(text);

    if (!(chain instanceof CriticCommentChain))
      throw CriticError("invalid chain argument; expected CommentChain object");
    if (chain.review.id != this.review.id)
      throw CriticError("invalid use; chain belongs to a different review");

    if (!text)
      throw CriticError("invalid use: can't add empty comment");

    if (chain.id in internals.replied_to_chains)
      throw CriticError("can't add two replies to a comment chain in one batch");
    internals.replied_to_chains[chain.id] = true;

    operations.push(function (batch_id)
      {
        var comment_id = db.execute("INSERT INTO comments (chain, batch, uid, state, comment) VALUES (%d, %d, %d, 'current', %s) RETURNING id",
                                    chain.id, batch_id, this.user.id, text)[0].id;

        for (var user_id in chain.users)
          if (user_id != this.user.id)
            db.execute("INSERT INTO commentstoread (uid, comment) VALUES (%d, %d)", user_id, comment_id);

        if (!db.execute("SELECT 1 FROM commentchainusers WHERE chain=%d AND uid=%d", chain.id, this.user.id)[0])
          db.execute("INSERT INTO commentchainusers (chain, uid) VALUES (%d, %d)", chain.id, this.user.id);
      });
  };

CriticBatch.prototype.resolveIssue = function (chain)
  {
    var internals = batch_internals[this.__id__];
    var operations = internals.comment_operations;

    if (!(chain instanceof CriticCommentChain))
      throw CriticError("invalid chain argument; expected CommentChain object");
    if (chain.review.id != this.review.id)
      throw CriticError("invalid use; chain belongs to a different review");

    if (chain.state != CriticCommentChain.STATE_OPEN)
      throw CriticError("can't resolve issue; already addressed or resolved");

    if (chain.id in internals.modified_issues)
      throw CriticError("can't modify the state of an issue more than once in a single batch");
    internals.modified_issues[chain.id] = true;

    operations.push(function (batch_id)
      {
        db.execute("UPDATE commentchains SET state='closed', closed_by=%d WHERE id=%d", this.user.id, chain.id);
        db.execute("INSERT INTO commentchainchanges (review, batch, uid, chain, state, from_state, to_state) VALUES (%d, %d, %d, %d, 'performed', %s, %s)",
                   this.review.id, batch_id, this.user.id, chain.id, 'open', 'closed');

        if (!db.execute("SELECT 1 FROM commentchainusers WHERE chain=%d AND uid=%d", chain.id, this.user.id)[0])
          db.execute("INSERT INTO commentchainusers (chain, uid) VALUES (%d, %d)", chain.id, this.user.id);
      });
  };

CriticBatch.prototype.reopenIssue = function (chain, data)
  {
    var internals = batch_internals[this.__id__];
    var operations = internals.comment_operations;

    if (!(chain instanceof CriticCommentChain))
      throw CriticError("invalid chain argument; expected CommentChain object");
    if (chain.review.id != this.review.id)
      throw CriticError("invalid use; chain belongs to a different review");
    if (chain.type != CriticCommentChain.TYPE_ISSUE)
      throw CriticError("invalid use: cannot reopen notes");

    if (chain.id in internals.modified_issues)
      throw CriticError("can't modify the state of an issue more than once in a single batch");
    internals.modified_issues[chain.id] = true;

    var current_state;
    switch (chain.state)
    {
    case CriticCommentChain.STATE_ADDRESSED: current_state = "addressed"; break;
    case CriticCommentChain.STATE_RESOLVED: current_state = "closed"; break;
    default: writeln(chain.state); throw CriticError("can't ropen issue; not addressed or resolved");
    }

    var lines;
    if (chain.file)
    {
      if (chain.state == CriticCommentChain.STATE_ADDRESSED || data && data.fileVersion)
      {
        if (!data || !data.fileVersion || !(data.fileVersion instanceof CriticFileVersion))
          throw CriticError("data.fileVersion: invalid argument; expected file version object");
        if (typeof data.lineIndex != "number")
          throw CriticError("data.lineIndex: invalid argument; expected number");
        if (typeof data.lineCount != "number")
          throw CriticError("data.lineCount: invalid argument; expected number");

        var file_version = data.fileVersion;
        var propagation_back = propagateCommentChain(this.review, file_version, data.lineIndex, data.lineCount, false, chain);
        var propagation_forward = propagateCommentChain(this.review, file_version, data.lineIndex, data.lineCount, true, chain);

        switch (propagation_forward[1])
        {
        case "clean":
          break;
        case "merge":
          throw CriticError(format("cannot reopen issue; commit is followed by a merge commit: %s", propagation_forward[2].sha1));
        case "modified":
          throw CriticError(format("cannot reopen issue; lines are modified by a later commit: %s", propagation_forward[2].sha1));
        }

        var sha1s = {};

        lines = [[commitFromFileVersion(file_version), file_version.sha1, data.lineIndex, data.lineCount]]
                  .concat(propagation_back[0], propagation_forward[0])
                  .filter(function (data) { if (data[1] in sha1s) return false; sha1s[data[1]] = true; return true; });
      }
    }
    else
      lines = null;

    operations.push(function (batch_id)
      {
        db.execute("UPDATE commentchains SET state='open', closed_by=null, addressed_by=null WHERE id=%d", chain.id);
        db.execute("INSERT INTO commentchainchanges (review, batch, uid, chain, state, from_state, to_state) VALUES (%d, %d, %d, %d, 'performed', %s, %s)",
                   this.review.id, batch_id, this.user.id, chain.id, current_state, 'open');

        if (lines)
          for (var index = 0; index < lines.length; ++index)
          {
            var line = lines[index];

            db.execute("INSERT INTO commentchainlines (chain, uid, state, commit, sha1, first_line, last_line) VALUES (%d, %d, 'current', %d, %s, %d, %d)",
                       chain.id, this.user.id, line[0].id, line[1], line[2] + 1, line[2] + line[3]);
          }
      });
  };

CriticBatch.prototype.markIssueAddressedBy = function (chain, commit)
  {
    var internals = batch_internals[this.__id__];
    var operations = internals.comment_operations;

    if (!(chain instanceof CriticCommentChain))
      throw CriticError("invalid chain argument; expected CommentChain object");
    if (chain.review.id != this.review.id)
      throw CriticError("invalid use; chain belongs to a different review");

    if (!(commit instanceof CriticCommit))
      throw CriticError("invalid commit argument; expected Commit object");
    if (!(commit.sha1 in this.review.commits))
      throw CriticError("invalid use; issues can only be addressed by commits in the review");

    if (chain.state != CriticCommentChain.STATE_OPEN)
      throw CriticError("can't address issue; already addressed or resolved");

    if (chain.id in internals.modified_issues)
      throw CriticError("can't modify the state of an issue more than once in a single batch");
    internals.modified_issues[chain.id] = true;

    operations.push(function (batch_id)
      {
        db.execute("UPDATE commentchains SET state='addressed', closed_by=%d, addressed_by=%d WHERE id=%d", this.user.id, commit.id, chain.id);
        db.execute("INSERT INTO commentchainchanges (review, batch, uid, chain, state, from_state, to_state) VALUES (%d, %d, %d, %d, 'performed', %s, %s)",
                   this.review.id, batch_id, this.user.id, chain.id, 'open', 'addressed');

        if (!db.execute("SELECT 1 FROM commentchainusers WHERE chain=%d AND uid=%d", chain.id, this.user.id)[0])
          db.execute("INSERT INTO commentchainusers (chain, uid) VALUES (%d, %d)", chain.id, this.user.id);
      });
  };

/*
function changeReviewFileStatus(what, new_state)
{
  if (what instanceof CriticChangeset)
  {
    if (what.review != this.review)
      throw CriticError("invalid changeset; must associated with the batch's review");

    result = db.execute("SELECT id, file, deleted, inserted FROM reviewfiles WHERE review=%d AND changeset=%d AND state!=%s", this.review.id, what.id, new_state);
  }
  else if (what instanceof CriticChangesetFile)
  {
    if (what.changeset.review != this.review)
      throw CriticError("invalid file; must be part of a changeset associated with the batch's review");

    result = db.execute("SELECT id, file, deleted, inserted FROM reviewfiles WHERE review=%d AND changeset=%d AND file=%d AND state!=%s", this.review.id, what.changeset.id, what.id, new_state);
  }
  else
  {
    result = [];

    for (var index = 0; index < what.length; ++index)
    {
      var rows = db.execute("SELECT reviewfiles.id, file, deleted, inserted FROM reviewfiles JOIN changesets ON (changeset=changesets.id) WHERE review=%d AND child=%d AND state!=%s", this.review.id, what[index].id, new_state);
      for (var row_index = 0; row_index < rows.length; ++row_index)
        result.push(rows[row_index]);
    }
  }
}
*/

function changeAssignments(user, what, assigned)
{
  var result;

  if (what instanceof CriticChangeset)
  {
    if (what.review != this.review)
      throw CriticError("invalid changeset; must associated with the batch's review");

    result = db.execute("SELECT id, file, deleted, inserted FROM reviewfiles WHERE review=%d AND changeset=%d", this.review.id, what.id);
  }
  else if (what instanceof CriticChangesetFile)
  {
    if (what.changeset.review != this.review)
      throw CriticError("invalid file; must be part of a changeset associated with the batch's review");

    result = db.execute("SELECT id, file, deleted, inserted FROM reviewfiles WHERE review=%d AND changeset=%d AND file=%d", this.review.id, what.changeset.id, what.id);
  }
  else
  {
    result = [];

    for (var index = 0; index < what.length; ++index)
    {
      var rows = db.execute("SELECT reviewfiles.id, file, deleted, inserted FROM reviewfiles JOIN changesets ON (changeset=changesets.id) WHERE review=%d AND child=%d", this.review.id, what[index].id);
      for (var row_index = 0; row_index < rows.length; ++row_index)
        result.push(rows[row_index]);
    }
  }

  var assignments = batch_internals[this.__id__].assignments;
  var files = assignments[user.id];

  if (!files)
  {
    files = assignments[user.id] = {};
    Object.defineProperty(files, "fileCount", { value: 0, writable: true });
  }

  for (var index = 0; index < result.length; ++index)
  {
    var row = result[index];
    var file = files[row.file];

    if (!file)
      file = files[row.file] =
        {
          assignedFiles: {}, assignedDeleteCount: 0, assignedInsertCount: 0,
          unassignedFiles: {}, unassignedDeleteCount: 0, unassignedInsertCount: 0
        };

    if (assigned)
    {
      if (row.id in file.unassignedFiles)
      {
        delete file.unassignedFiles[row.id];
        file.unassignedDeleteCount -= row.deleted;
        file.unassignedInsertCount -= row.inserted;
      }
      else
      {
        ++assignments.fileCount;
        ++files.fileCount;
      }

      file.assignedFiles[row.id] = true;
      file.assignedDeleteCount += row.deleted;
      file.assignedInsertCount += row.inserted;
    }
    else
    {
      if (row.id in file.assignedFiles)
      {
        delete file.assignedFiles[row.id];
        file.assignedDeleteCount -= row.deleted;
        file.assignedInsertCount -= row.inserted;
      }
      else
      {
        ++assignments.fileCount;
        ++files.fileCount;
      }

      file.unassignedFiles[row.id] = true;
      file.unassignedDeleteCount += row.deleted;
      file.unassignedInsertCount += row.inserted;
    }
  }
}

CriticBatch.prototype.assignChanges = function (user, what) { changeAssignments.call(this, user, what, true); };
CriticBatch.prototype.unassignChanges = function (user, what) { changeAssignments.call(this, user, what, false); };

CriticBatch.prototype.addReviewFilter = function (user, type, path)
  {
    if (!(this instanceof CriticBatch))
      throw CriticError("invalid this object; expected batch object");

    type = String(type);
    path = String(path);

    if (!(user instanceof CriticUser))
      throw CriticError("invalid user argument; expected User object");
    if (type != "reviewer" && type != "watcher" && type != "ignored")
      throw CriticError("invalid type argument; expected 'reviewer', 'watcher' or 'ignored'");
    if (/[^\/]\*\*|\*\*[^\/]/.test(path))
      throw CriticError("invalid wildcards in path argument");

    var internals = batch_internals[this.__id__];
    var user_ids = internals.filter_user_ids;
    var operations = internals.filter_operations;
    var added_filters = internals.added_filters;
    var removed_filters = internals.removed_filters;

    for (var index = 0; index < removed_filters.length; ++index)
    {
      var removed_filter = removed_filters[index];
      if (removed_filter.uid == user.id && removed_filter.path == path)
        throw CriticError("can't add filter; identical or conflicting filter removed in this batch");
    }

    var result = db.execute("SELECT 1 FROM reviewfilters WHERE review=%d AND uid=%d AND path=%s", this.review.id, user.id, path);

    if (result.length != 0)
      throw CriticError("can't add filter; identical or conflicting filter already exists");

    for (var index = 0; index < added_filters.length; ++index)
    {
      var added_filter = added_filters[index];
      if (added_filter.uid == user.id && added_filter.path == path)
        throw CriticError("can't add filter; identical or conflicting filter added in this batch");
    }

    user_ids[user.id] = user;
    added_filters.push({ uid: user.id, path: path, type: type, delegate: null });

    operations.push(function (transaction_id)
      {
        db.execute("INSERT INTO reviewfilters (review, uid, path, type, creator) VALUES (%d, %d, %s, %s, %d)",
                   this.review.id, user.id, path, type, this.user.id);

        db.execute("INSERT INTO reviewfilterchanges (transaction, uid, path, type, created) VALUES (%d, %d, %s, %s, true)",
                   transaction_id, user.id, path, type);
      });
  };

CriticBatch.prototype.removeReviewFilter = function (user, type, path)
  {
    if (!(this instanceof CriticBatch))
      throw CriticError("invalid this object; expected batch object");

    type = String(type);
    path = String(path);

    if (!(user instanceof CriticUser))
      throw CriticError("invalid user argument; expected User object");
    if (type != "reviewer" && type != "watcher" && type != "ignored")
      throw CriticError("invalid type argument; expected 'reviewer', 'watcher' or 'ignored'");

    var internals = batch_internals[this.__id__];
    var user_ids = internals.filter_user_ids;
    var operations = internals.filter_operations;
    var added_filters = internals.added_filters;
    var removed_filters = internals.removed_filters;

    for (var index = 0; index < added_filters.length; ++index)
    {
      var added_filter = added_filters[index];
      if (added_filter.uid == user.id && added_filter.path == path)
        throw CriticError("can't remove filter; identical or conflicting filter added in this batch");
    }

    var result = db.execute("SELECT 1 FROM reviewfilters WHERE review=%d AND uid=%d AND path=%s AND type=%s", this.review.id, user.id, path, type)[0];

    if (!result)
      throw CriticError("can't remove filter; no such filter exists");

    for (var index = 0; index < removed_filters.length; ++index)
    {
      var removed_filter = removed_filters[index];
      if (removed_filter.uid == user.id && removed_filter.path == path && removed_filter.type == type)
        /* Already being removed; ignore this call. */
        return;
    }

    user_ids[user.id] = user;
    removed_filters.push({ uid: user.id, path: path, type: type, delegate: null });

    operations.push(
      function (transaction_id)
      {
        db.execute("DELETE FROM reviewfilters WHERE review=%d AND uid=%d AND path=%s", this.review.id, user.id, path);

        db.execute("INSERT INTO reviewfilterchanges (transaction, uid, type, created) VALUES (%d, %d, %s, %s, false)",
                   transaction_id, user.id, path, type);
      });
  };

function getReviewMessageId(review, to_user)
{
  var result = db.execute("SELECT messageid, hostname FROM reviewmessageids WHERE review=%d AND uid=%d", review.id, to_user.id)[0];

  if (result)
    return format("<%s@%s>", result.messageid, result.hostname.trim());
  else
    return null;
}

function getCommentMessageId(comment, to_user)
{
  var result = db.execute("SELECT messageid, hostname FROM commentmessageids WHERE comment=%d AND uid=%d", comment.id, to_user.id)[0];

  if (result)
    return format("<%s@%s>", result.messageid, result.hostname.trim());
  else
    return null;
}

CriticBatch.prototype.finish = function (data)
  {
    if (!(this instanceof CriticBatch))
      throw CriticError("invalid this object; expected batch object");

    /* We commit at the end of the function.  To ensure we don't commit anything
       we didn't mean to, roll back the current transaction first.  (Normally,
       there wouldn't be anything in the current transaction to commit, but
       better safe than sorry. */
    db.rollback();

    try
    {
      data = data || {};

      var text = data.text && String(data.text);
      var internals = batch_internals[this.__id__];
      var filter_operations = internals.filter_operations;
      var filter_user_ids = internals.filter_user_ids;
      var added_filters = internals.added_filters;
      var removed_filters = internals.added_filters;
      var comment_operations = internals.comment_operations;
      var assignments = internals.assignments;
      var review_id = this.review.id;
      var batch_id = null;
      var transaction_id = null;
      var progress_before = this.review.progress;

      if (comment_operations.length)
        batch_id = db.execute("INSERT INTO batches (review, uid) VALUES (%d, %d) RETURNING id", this.review.id, this.user.id)[0].id;
      if (filter_operations.length || assignments.fileCount)
        transaction_id = db.execute("INSERT INTO reviewassignmentstransactions (review, assigner) VALUES (%d, %d) RETURNING ID", this.review.id, this.user.id)[0].id;

      if (filter_operations.length)
      {
        var filters_before = new CriticFilters({ review: this.review });
        var filters_after = new CriticFilters({ review: this.review,
                                                added_review_filters: added_filters,
                                                removed_review_filters: removed_filters });

        for (var index = 0; index < filter_operations.length; ++index)
        {
          var followup = filter_operations[index].call(this, transaction_id);
          if (followup)
            filter_operations.push(followup);
        }

        var commits = this.review.commits;
        var changesets = [];

        for (var cindex = 0; cindex < commits.length; ++cindex)
        {
          var changeset = this.review.getChangeset(commits[cindex]);

          if (changeset instanceof CriticMergeChangeset)
            for (var index = 0; index < changeset.changesets.length; ++index)
              changesets.push(changeset.changesets[index]);
          else
            changesets.push(changeset);
        }

        for (var user_id in filter_user_ids)
        {
          var user = filter_user_ids[user_id];

          for (var csindex = 0; csindex < changesets.length; ++csindex)
          {
            var changeset = changesets[csindex];
            var files = changeset.files;

            for (var findex = 0; findex < files.length; ++findex)
            {
              var file = files[findex];
              var reviewer_before = filters_before.isReviewer(user.id, file.id);
              var reviewer_after = filters_after.isReviewer(user.id, file.id);

              if (!reviewer_before && reviewer_after)
              {
                if (!user.isAuthor(changeset.child))
                  this.assignChanges(user, file);
              }
              else if (reviewer_before && !reviewer_after)
                this.unassignChanges(user, file);
            }
          }
        }
      }

      if (assignments.fileCount)
        for (var user_id in assignments)
        {
          var files = assignments[user_id], values;

          for (var file_id in files)
          {
            var file = files[file_id];
            var assignedFiles = file.assignedFiles;
            var unassignedFiles = file.unassignedFiles;

            values = Object.keys(assignedFiles);
            if (values.length)
            {
              var result = db.execute(format("SELECT id, deleted, inserted FROM reviewfiles JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id) WHERE review=%d AND uid=%d", review_id, user_id));
              for (var index = 0; index < result.length; ++index)
              {
                var row = result[index];
                if (assignedFiles[row.id])
                {
                  delete assignedFiles[row.id];
                  file.assignedDeleteCount -= row.deleted;
                  file.assignedInsertCount -= row.inserted;
                }
              }
            }

            values = Object.keys(assignedFiles).map(function (file_id) { return format("(%d,%d)", file_id, user_id); });
            if (values.length)
            {
              if (db.execute("SELECT 1 FROM reviewusers WHERE review=%d AND uid=%d", review_id, user_id).length == 0)
                db.execute("INSERT INTO reviewusers (review, uid) VALUES (%d, %d)", review_id, user_id);

              db.execute("INSERT INTO reviewuserfiles (file, uid) VALUES " + values);
              db.execute("INSERT INTO reviewassignmentchanges (transaction, file, uid, assigned) VALUES " +
                         Object.keys(assignedFiles).map(function (file_id) { return format("(%d,%d,%d,true)", transaction_id, file_id, user_id); }));
            }
            file.assignedFileCount = values.length;

            values = Object.keys(unassignedFiles);
            if (values.length)
            {
              var result = db.execute(format("SELECT COUNT(*) AS count, SUM(deleted) AS deleted, SUM(inserted) AS inserted FROM reviewfiles JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id) WHERE review=%%d AND uid=%%d AND id IN (%s)", values), review_id, user_id)[0];

              db.execute(format("DELETE FROM reviewuserfiles WHERE file IN (%s) AND uid=%d", values, user_id));
              db.execute("INSERT INTO reviewassignmentchanges (transaction, file, uid, assigned) VALUES " +
                         Object.keys(unassignedFiles).map(function (file_id) { return format("(%d,%d,%d,false)", transaction_id, file_id, user_id); }));

              file.unassignedFileCount = result.count;
              file.unassignedDeleteCount = result.deleteCount;
              file.unassignedInsertCount = result.insertCount;
            }
          }
        }

      if (comment_operations.length)
        for (var index = 0; index < comment_operations.length; ++index)
          comment_operations[index].call(this, batch_id);

      db.execute("UPDATE reviews SET serial=serial+1 WHERE id=%d", this.review.id);

      var updated_review = new CriticReview(this.review.id);
      var progress_after = updated_review.progress;

      db.commit();

      if (!data.silent)
      {
        var argv = [python_executable, "-m", "cli"], stdin = "";

        if (batch_id !== null)
        {
          argv.push("generate-mails-for-batch");
          stdin += format("%s\n", JSON.stringify({ batch_id: batch_id,
                                                   was_accepted: progress_before.accepted,
                                                   is_accepted: progress_after.accepted }));
        }

        if (transaction_id !== null)
        {
          argv.push("generate-mails-for-assignments-transaction");
          stdin += format("%s\n", JSON.stringify({ transaction_id: transaction_id }));
        }

        var process = new OS.Process(python_executable,
                                     { argv: argv,
                                       environ: { PYTHONPATH: python_path }});
        var lines = process.call(stdin).trim().split("\n");

        if (lines)
        {
          for (var index = 0; index < lines.length; ++index)
            JSON.parse(lines[index]).forEach(sendMail);

          var pid = parseInt(IO.File.read(maildelivery_pid_path).decode().trim());

          OS.Process.kill(pid, 1);
        }
      }
    }
    finally
    {
      /* If anything fails we don't want to have done anything at all to the
         database, so roll the transaction back.  If we did finish, we just
         committed the transaction, in which case we aren't in a transaction
         right no, and the rollback() call is a no-op. */
      db.rollback();
    }
  };
