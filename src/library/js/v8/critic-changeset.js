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

var CriticChangesetLineConstants = { TYPE_CONTEXT:    0,
                                     TYPE_WHITESPACE: 1,
                                     TYPE_REPLACED:   2,
                                     TYPE_MODIFIED:   3,
                                     TYPE_DELETED:    4,
                                     TYPE_INSERTED:   5,

                                     OPERATION_REPLACE: 0,
                                     OPERATION_DELETE:  1,
                                     OPERATION_INSERT:  2 };

function CriticChangesetLine(type, old_index, old_lines, new_index, new_lines, operations)
{
  this.type = type;
  this.oldIndex = old_index;
  this.oldText = old_lines && old_lines[old_index];
  this.newIndex = new_index;
  this.newText = new_lines && new_lines[new_index];

  operations = operations || null;

  var self = this;

  function getOperations()
  {
    if (typeof operations == "string")
    {
      operations = operations.split(",");

      for (var index = 0; index < operations.length; ++index)
      {
        var operation = operations[index], match;

        if (operation == "ws")
          continue;

        if (match = /^r(\d+)-(\d+)=(\d+)-(\d+)$/.exec(operation))
          operation = [CriticChangesetLineConstants.OPERATION_REPLACE, parseInt(match[1]), parseInt(match[2]), parseInt(match[3]), parseInt(match[4])];
        else if (match = /^d(\d+)-(\d+)$/.exec(operation))
          operation = [CriticChangesetLineConstants.OPERATION_DELETE, parseInt(match[1]), parseInt(match[2])];
        else if (match = /^i(\d+)-(\d+)$/.exec(operation))
          operation = [CriticChangesetLineConstants.OPERATION_INSERT, parseInt(match[1]), parseInt(match[2])];

        Object.freeze(operation);

        operations[index] = operation;
      }

      Object.freeze(operations);
    }

    return operations;
  }

  Object.defineProperty(this, "operations", { get: getOperations, enumerable: true });
  Object.freeze(this);
}

function CriticChangesetChunk(changeset, file, delete_offset, delete_count, insert_offset, insert_count, analysis, whitespace)
{
  this.changeset = changeset;
  this.file = file;
  this.deleteOffset = delete_offset;
  this.deleteCount = delete_count;
  this.insertOffset = insert_offset;
  this.insertCount = insert_count;

  var self = this;
  var lines;

  function getLines()
  {
    function fillLines(old_stop, new_stop)
    {
      while (old_offset < old_stop && new_offset < new_stop)
        lines.push(new CriticChangesetLine(CriticChangesetLineConstants.TYPE_REPLACED, self.deleteOffset + old_offset++, old_lines, self.insertOffset + new_offset++, new_lines));
      while (old_offset < old_stop)
        lines.push(new CriticChangesetLine(CriticChangesetLineConstants.TYPE_DELETED, self.deleteOffset + old_offset++, old_lines, self.insertOffset + new_offset, null));
      while (new_offset < new_stop)
        lines.push(new CriticChangesetLine(CriticChangesetLineConstants.TYPE_INSERTED, self.deleteOffset + old_offset, null, self.insertOffset + new_offset++, new_lines));
    }

    if (!lines)
    {
      var old_lines = file.oldVersion.lines;
      var new_lines = file.newVersion.lines;
      var old_offset = 0, new_offset = 0;

      lines = [];

      if (analysis)
      {
        var mappings = analysis.split(";");

        for (var mapping_index = 0; mapping_index < mappings.length; ++mapping_index)
        {
          var match = /^(\d+)=(\d+)(?::(.*))?$/.exec(mappings[mapping_index]);
          var old_mapped_offset = parseInt(match[1]);
          var new_mapped_offset = parseInt(match[2]);
          var operations = match[3];

          fillLines(old_mapped_offset, new_mapped_offset);

          lines.push(new CriticChangesetLine(CriticChangesetLineConstants.TYPE_MODIFIED, self.deleteOffset + old_offset++, old_lines, self.insertOffset + new_offset++, new_lines, operations));
        }
      }

      fillLines(self.deleteCount, self.insertCount);
    }

    return lines;
  }

  Object.defineProperty(this, "lines", { get: getLines, enumerable: true });
  Object.freeze(this);
}

CriticChangesetChunk.prototype.toString = function ()
  {
    var result = format("@@ -%d,%d +%d,%d @@\n", this.deleteOffset + 1, this.deleteCount, this.insertOffset + 1, this.insertCount);

    for (var index = 0; index < this.lines.length; ++index)
    {
      var line = this.lines[index];
      switch (line.type)
      {
      case CriticChangesetLineConstants.TYPE_REPLACED:
      case CriticChangesetLineConstants.TYPE_MODIFIED:
      case CriticChangesetLineConstants.TYPE_DELETED:
        result += format("-%s%s\n", line.oldText, line.operations ? " " + JSON.stringify(line.operations) : "");
      }
    }

    for (var index = 0; index < this.lines.length; ++index)
    {
      var line = this.lines[index];
      switch (line.type)
      {
      case CriticChangesetLineConstants.TYPE_REPLACED:
      case CriticChangesetLineConstants.TYPE_MODIFIED:
      case CriticChangesetLineConstants.TYPE_INSERTED:
        result += format("+%s%s\n", line.newText, line.operations ? " " + JSON.stringify(line.operations) : "");
      }
    }

    return result;
  };

function CriticChangesetFile(changeset, file_id, old_sha1, new_sha1, old_mode, new_mode)
{
  CriticFile.call(this, { id: file_id });

  this.changeset = changeset;

  if (old_sha1 != '0000000000000000000000000000000000000000')
    this.oldVersion = new CriticChangesetFileVersion(changeset, this, old_mode, null, old_sha1);
  else
    this.oldVersion = null;
  if (new_sha1 != '0000000000000000000000000000000000000000')
    this.newVersion = new CriticChangesetFileVersion(changeset, this, new_mode, null, new_sha1);
  else
    this.newVersion = null;

  var self = this;
  var chunks, deleteCount, insertCount;
  var reviewers;

  function getChunks()
  {
    if (chunks === void 0)
    {
      if (self.oldVersion === null || self.newVersion === null)
        chunks = null;
      else
      {
        chunks = [];

        var result = db.execute("SELECT deleteOffset, deleteCount, insertOffset, insertCount, analysis, whitespace FROM chunks WHERE changeset=%d AND file=%d ORDER BY deleteOffset ASC", self.changeset.id, self.id);

        for (var index = 0; index < result.length; ++index)
        {
          var row = result[index];
          chunks.push(new CriticChangesetChunk(self.changeset, self, row.deleteOffset - 1, row.deleteCount, row.insertOffset - 1, row.insertCount, row.analysis, !!row.whitespace));
        }
      }
    }

    return chunks;
  }

  function fetchCounts()
  {
    var result = db.execute("SELECT SUM(deletecount) AS deleteCount, SUM(insertcount) AS insertCount FROM chunks WHERE changeset=%d AND file=%d",
                            self.changeset.id, self.id)[0];

    deleteCount = result.deleteCount;
    insertCount = result.insertCount;
  }

  function getDeleteCount()
  {
    if (deleteCount === void 0)
      fetchCounts();

    return deleteCount;
  }

  function getInsertCount()
  {
    if (insertCount === void 0)
      fetchCounts();

    return insertCount;
  }

  function getReviewers()
  {
    if (!reviewers)
      if (!self.changeset.review)
        return null;
      else
      {
        reviewers = {};

        Object.defineProperties(reviewers, { pending: { value: {} },
                                             reviewed: { value: {} }});

        var result = db.execute("SELECT assignee, state, SUM(deleted) AS deleted, SUM(inserted) AS inserted" +
                                 " FROM fullreviewuserfiles" +
                                " WHERE review=%d AND changeset=%d AND file=%d AND (state='pending' OR reviewer=assignee)" +
                             " GROUP BY assignee, state",
                                self.changeset.review.id, self.changeset.id, self.id);

        for (var index = 0; index < result.length; ++index)
        {
          var row = result[index];
          var user_id = row.assignee;

          if (!(user_id in reviewers))
            reviewers[user_id] = new CriticUser(user_id);

          var counts = Object.freeze(Object.create(null, { deleteCount: { value: row.deleted, enumerable: true },
                                                           insertCount: { value: row.inserted, enumerable: true }}));

          if (row.state == "pending")
            reviewers.pending[user_id] = counts;
          else
            reviewers.reviewed[user_id] = counts;
        }

        Object.freeze(reviewers.pending);
        Object.freeze(reviewers.reviewed);
        Object.freeze(reviewers);
      }

    return reviewers;
  }

  var isReviewed, reviewedBy;

  if (!changeset.review)
    isReviewed = reviewedBy = null;

  function fetchReviewStatus()
  {
    var result = db.execute("SELECT state, reviewer FROM reviewfiles WHERE review=%d AND changeset=%d AND file=%d",
                            self.changeset.review.id, self.changeset.id, self.id)[0];

    isReviewed = result.state == "reviewed";
    reviewedBy = isReviewed ? new CriticUser({ id: result.reviewer }) : null;
  }

  function getIsReviewed()
  {
    if (isReviewed === void 0)
      fetchReviewStatus();

    return isReviewed;
  }

  function getReviewedBy()
  {
    if (reviewedBy === void 0)
      fetchReviewStatus();

    return reviewedBy;
  }

  Object.defineProperties(this, { chunks: { get: getChunks, enumerable: true },
                                  deleteCount: { get: getDeleteCount, enumerable: true },
                                  insertCount: { get: getInsertCount, enumerable: true },
                                  reviewers: { get: getReviewers, enumerable: true },
                                  isReviewed: { get: getIsReviewed, enumerable: true },
                                  reviewedBy: { get: getReviewedBy, enumerable: true }});
  Object.freeze(this);
}

function CriticChangesetFileVersion(changeset, file, mode, size, sha1)
{
  CriticFileVersion.call(this, changeset.repository, file.path, mode, size, sha1, { review: changeset.review });

  this.changeset = changeset;
  this.file = file;

  Object.freeze(this);
}

CriticChangesetFileVersion.prototype = Object.create(CriticFileVersion.prototype);

CriticChangesetFile.prototype.toString = function () { return format("CriticChangesetFile(path=%s)", this.path); };

function CriticChangeset(repository, data)
{
  var changeset_id, parent, child;

  if (typeof data.id == "number")
  {
    changeset_id = data.id;

    var result = db.execute("SELECT parent, child FROM changesets WHERE id=%d", changeset_id)[0];

    if (!result)
      throw CriticError(format("%d: invalid changeset ID", changeset_id));

    parent = data.parent || repository.getCommit(result.parent);
    child = data.child || repository.getCommit(result.child);

    result = null;
  }
  else if (data.parent && data.child)
  {
    parent = data.parent;
    child = data.child;

    var result = db.execute("SELECT id FROM changesets WHERE parent=%d AND child=%d AND type IN ('direct', 'custom')", parent.id, child.id)[0];

    if (!result)
      throw CriticError(format("%s..%s: changeset not cached", parent.sha1, child.sha1));

    changeset_id = result.id;

    result = null;
  }
  else
    throw CriticError("invalid use: either changeset ID or parent/child commits must be provided");

  this.repository = repository;
  this.review = data.review || null;
  this.id = changeset_id;
  this.parent = parent;
  this.child = child;
  this.commits = data.commits;

  var self = this;
  var files = null, filtered_files = data.files || false;
  var reviewers = null;
  var actuals = null;

  function getFiles()
  {
    if (!files)
    {
      files = [];

      var file_filter;
      if (filtered_files)
        file_filter = format(" AND file IN (%s)", filtered_files.map(parseInt).join(", "));
      else
        file_filter = "";

      var result = db.execute("SELECT file, old_sha1, new_sha1, old_mode, new_mode FROM fileversions WHERE changeset=%d" + file_filter, self.id);

      for (var index = 0; index < result.length; ++index)
      {
        var row = result[index];
        var file = new CriticChangesetFile(self, row.file, row.old_sha1, row.new_sha1, row.old_mode, row.new_mode);

        files.push(file);

        Object.defineProperty(files, file.path, { value: file });
      }

      Object.freeze(files);
    }

    return files;
  }

  function getReviewers()
  {
    if (!reviewers)
      if (!self.review)
        return null;
      else
      {
        reviewers = {};

        Object.defineProperties(reviewers, { pending: { value: {} },
                                             reviewed: { value: {} }});

        var result = db.execute("SELECT assignee, state, SUM(deleted) AS deleted, SUM(inserted) AS inserted" +
                                 " FROM fullreviewuserfiles" +
                                " WHERE review=%d AND changeset=%d AND (state='pending' OR reviewer=assignee)" +
                             " GROUP BY assignee, state", self.review.id, self.id);

        for (var index = 0; index < result.length; ++index)
        {
          var row = result[index];
          var user_id = row.assignee;

          if (!(user_id in reviewers))
            reviewers[user_id] = new CriticUser(user_id);

          var counts = Object.freeze(Object.create(null, { deleteCount: { value: row.deleted, enumerable: true },
                                                           insertCount: { value: row.inserted, enumerable: true }}));

          if (row.state == "pending")
            reviewers.pending[user_id] = counts;
          else
            reviewers.reviewed[user_id] = counts;
        }

        Object.freeze(reviewers.pending);
        Object.freeze(reviewers.reviewed);
        Object.freeze(reviewers);
      }

    return reviewers;
  }

  function getActuals()
  {
    if (actuals === null)
      if (!self.review)
        return null;
      else
      {
        actuals = [];

        if (db.execute("SELECT 1 FROM reviewchangesets WHERE review=%d AND changeset=%d", self.review.id, self.id)[0])
          actuals.push(self);
        else
        {
          var commits = self.review.commits.restrict([self.child], [self.parent]);

          for (var index = 0; index < commits.length; ++index)
          {
            if (commits[index].parents.length > 1)
            {
              var merge = self.review.repository.getMergeChangeset(commits[index], { review: self.review });
              merge.changesets.forEach(function (changeset) { actuals.push(changeset); });
            }
            else
              actuals.push(self.review.repository.getChangeset({ commit: commits[index], review: self.review }));
          }
        }

        Object.freeze(actuals);
      }

    return actuals;
  }

  Object.defineProperties(this, { files: { get: getFiles, enumerable: true },
                                  reviewers: { get: getReviewers, enumerable: true },
                                  actuals: { get: getActuals, enumerable: true }});

  Object.freeze(this);
}

function CriticMergeChangeset(changesets)
{
  this.repository = changesets[0].repository;
  this.review = changesets[0].review;
  this.commit = changesets[0].child;
  this.changesets = [];

  for (var index = 0; index < changesets.length; ++index)
  {
    this.changesets.push(changesets[index]);
    this.changesets[changesets[index].parent.sha1] = changesets[index];
  }

  Object.freeze(this.changesets);
  Object.freeze(this);
}
