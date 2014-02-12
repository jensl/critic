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

function CriticStatistics()
{
  this.review = null;
  this.repository = null;
  this.interval_start = null;
  this.interval_end = null;
  this.user = null;
  this.directories = null;
  this.files = null;

  Object.seal(this);
}

CriticStatistics.prototype.setReview = function (review)
  {
    if (!(review instanceof CriticReview))
      throw CriticError("invalid argument; expected Review object");

    this.review = review;
  };

CriticStatistics.prototype.setRepository = function (repository)
  {
    if (!(repository instanceof CriticRepository))
      throw CriticError("invalid argument; expected Repository object");

    this.repository = repository;
  };

CriticStatistics.prototype.setInterval = function (start, end)
  {
    function mangle(item, argument)
    {
      if (Object.prototype.toString.call(item) == "[object Date]")
        return item;

      var string = String(item);

      if (/^\d+ (?:second|minute|hour|day|week|month|year)s?$/.test(string))
        return string;
      else
        throw CriticError(format("invalid %s argument; expected Date object or string specifying an interval", argument));
    }

    this.interval_start = mangle(start);

    if (end)
      this.interval_end = mangle(end);
  };

CriticStatistics.prototype.setUser = function (user)
  {
    if (!(user instanceof CriticUser))
      throw CriticError("invalid argument; expected User object");
    if (this.user)
      throw CriticError("invalid use; user already set");

    this.user = user;
  };

CriticStatistics.prototype.addDirectory = function (directory)
  {
    if (!this.directories)
      this.directories = [];

    this.directories.push(/^(.*)\/+$/.exec(String(directory))[1]);
  };

CriticStatistics.prototype.addFile = function (file)
  {
    if (!this.files)
      this.files = [];

    this.files.push(String(file));
  };

CriticStatistics.prototype.getReviewedLines = function (data)
  {
    var grouping = (data && data.grouping) || ["user"];

    if (!("length" in grouping))
      throw CriticError("invalid data.grouping argument; expected Array object");
    else if (!grouping.length)
      throw CriticError("invalid data.grouping argument; expected non-empty array");

    var grouping_columns = [];

    for (var index = 0; index < grouping.length; ++index)
      switch (grouping[index])
      {
      case "user":
        grouping_columns.push("reviewfilechanges.uid");
        break;
      case "file":
        grouping_columns.push("reviewfiles.file");
        break;
      case "review":
        grouping_columns.push("reviewfiles.review");
        break;
      default:
        throw CriticError(format("invalid data.grouping[%d] value; expected 'user', 'file' or 'review'", index));
      }

    grouping_columns = grouping_columns.join(", ");

    var filteredfiles_join;

    if (this.directories || this.files)
      filteredfiles_join = " filteredfiles JOIN reviewfiles ON (filteredfiles.file=reviewfiles.file)";
    else
      filteredfiles_join = " reviewfiles";

    var repository_join;

    if (this.repository)
      repository_join = " JOIN reviews ON (reviews.id=reviewfiles.review) JOIN branches ON (branches.id=reviews.branch)";
    else
      repository_join = "";

    var query = "SELECT " + grouping_columns + ", SUM(deleted) AS deleted, SUM(inserted) AS inserted FROM" + filteredfiles_join + " JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)" + repository_join + " WHERE reviewfilechanges.state='performed' AND reviewfilechanges.to='reviewed'";

    var params = {};

    if (this.review)
    {
      query += " AND (reviewfiles.review=%(review.id)d)";
      params["review.id"] = this.review.id;
    }

    if (this.repository)
    {
      query += " AND (branches.repository=%(repository.id)d)";
      params["repository.id"] = this.repository.id;
    }

    if (this.user)
    {
      query += " AND (reviewfilechanges.uid=%(user.id)d)";
      params["user.id"] = this.user.id;
    }

    if (this.directories || this.files)
    {
      db.execute("CREATE TEMPORARY TABLE filteredfiles ( file INTEGER PRIMARY KEY ) ON COMMIT DROP");

      if (this.directories)
        for (var index = 0; index < this.directories.length; ++index)
          db.execute("INSERT INTO filteredfiles (file) SELECT id FROM files WHERE path LIKE %s", this.directories[index] + "/%");

      if (this.files)
        for (var index = 0; index < this.files.length; ++index)
          db.execute("INSERT INTO filteredfiles (file) SELECT id FROM files WHERE MD5(path)=MD5(%s)", this.files[index]);
    }

    if (this.interval_start)
    {
      if (typeof this.interval_start === "object")
      {
        query += " AND (reviewfilechanges.time >= %(start)s::timestamp)";
        params["start"] = Date.prototype.toSQLTimestamp.call(this.interval_start);
      }
      else
      {
        query += " AND (reviewfilechanges.time >= now() - %(start)s::interval)";
        params["start"] = this.interval_start;
      }
    }

    if (this.interval_end)
    {
      if (typeof this.interval_end === "object")
      {
        query += " AND (reviewfilechanges.time <= %(end)s::timestamp)";
        params["end"] = Date.prototype.toSQLTimestamp.call(this.interval_end);
      }
      else
      {
        query += " AND (reviewfilechanges.time <= now() - %(end)s::interval)";
        params["end"] = this.interval_end;
      }
    }

    query += " GROUP BY " + grouping_columns;

    var result = db.execute(query, params);
    var all_data = {};

    for (var row_index = 0; row_index < result.length; ++row_index)
    {
      var row = result[row_index], data = all_data;

      for (var column_index = 0; column_index < grouping.length - 1; ++column_index)
        data = data[row[column_index]] || (data[row[column_index]] = {});

      var counts = data[row[column_index]] || (data[row[column_index]] = Object.create(null, { deleteCount: { value: 0, writable: true },
                                                                                               insertCount: { value: 0, writable: true }}));

      counts.deleteCount += row.deleted;
      counts.insertCount += row.inserted;
    }

    /* This drops the temporary table created above. */
    db.rollback();

    return all_data;
  };

CriticStatistics.prototype.getWrittenComments = function ()
  {
    var filteredfiles_join;

    if (this.directories || this.files)
      filteredfiles_join = " filteredfiles JOIN commentchains ON (filteredfiles.file=commentchains.file)";
    else
      filteredfiles_join = " commentchains";

    var chains_query = "SELECT uid, type, COUNT(id) AS count FROM" + filteredfiles_join + " WHERE state!='draft' AND state!='empty'";
    var comments_query = "SELECT comments.uid AS uid, COUNT(comments.id) AS count, SUM(CHARACTER_LENGTH(comments.comment)) AS characters FROM" + filteredfiles_join + " JOIN comments ON (comments.chain=commentchains.id) WHERE comments.state='current'";
    var params = {};

    if (this.review)
    {
      chains_query += " AND (review=%(review.id)d)";
      comments_query +=  " AND (review=%(review.id)d)";
      params["review.id"] = this.review.id;
    }

    if (this.user)
    {
      chains_query += " AND (uid=%(user.id)d)";
      comments_query += " AND (comments.uid=%(user.id)d)";
      params["user.id"] = this.user.id;
    }

    if (this.directories || this.files)
    {
      db.execute("CREATE TEMPORARY TABLE filteredfiles ( file INTEGER PRIMARY KEY ) ON COMMIT DROP");

      if (this.directories)
        for (var index = 0; index < this.directories.length; ++index)
          db.execute("INSERT INTO filteredfiles (file) SELECT id FROM files WHERE path LIKE %s", this.directories[index] + "/%");

      if (this.files)
        for (var index = 0; index < this.files.length; ++index)
          db.execute("INSERT INTO filteredfiles (file) SELECT id FROM files WHERE MD5(path)=MD5(%s)", this.files[index]);
    }

    if (this.interval_start)
    {
      if (typeof this.interval_start === "object")
      {
        chains_query += " AND (time >= %(start)s::timestamp)";
        comments_query += " AND (comments.time >= %(start)s::timestamp)";
        params["start"] = this.interval_start.toSQLTimestamp();
      }
      else
      {
        chains_query += " AND (time >= now() - %(start)s::interval)";
        comments_query += " AND (comments.time >= now() - %(start)s::interval)";
        params["start"] = this.interval_start;
      }
    }

    if (this.interval_end)
    {
      if (typeof this.interval_end === "object")
      {
        chains_query += " AND (time <= %(end)s::timestamp)";
        comments_query += " AND (comments.time <= %(end)s::timestamp)";
        params["end"] = this.interval_end.toSQLTimestamp();
      }
      else
      {
        chains_query += " AND (time <= now() - %(end)s::interval)";
        comments_query += " AND (comments.time <= now() - %(end)s::interval)";
        params["end"] = this.interval_end;
      }
    }

    chains_query += " GROUP BY uid, type";
    comments_query += " GROUP BY comments.uid";

    var data = {};

    function getPerUser(user_id)
    {
      return data[user_id] || (data[user_id] = Object.create(null, { raisedIssues: { value: 0, writable: true },
                                                                     writtenNotes: { value: 0, writable: true },
                                                                     totalComments: { value: 0, writable: true },
                                                                     totalCharacters: { value: 0, writable: true }}));
    }

    var result = db.execute(chains_query, params);
    for (var index = 0; index < result.length; ++index)
    {
      var row = result[index];
      var per_user = getPerUser(row.uid)

      if (row.type == "issue")
        per_user.raisedIssues += row.count;
      else
        per_user.writtenNotes += row.count;
    }

    var result = db.execute(comments_query, params);
    for (var index = 0; index < result.length; ++index)
    {
      var row = result[index];
      var per_user = getPerUser(row.uid)

      per_user.totalComments += row.count;
      per_user.totalCharacters += row.characters;
    }

    /* This drops the temporary table created above. */
    db.rollback();

    return data;
  };
