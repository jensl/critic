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

var review_internals = {};

function CriticReview_isCreated(review)
{
  return review_internals[review.id].created;
}

function CriticReviewFilter(review, user_id, path, type, creator_id)
{
  user_id = Number(user_id);
  path = String(path);
  creator_id = creator_id || Number(creator_id);

  this.review = review;
  this.path = path;
  this.type = type;

  var user = null;
  var creator = null;

  function getUser()
  {
    if (!user)
      user = new CriticUser(user_id);
    return user;
  }

  function getCreator()
  {
    if (!creator)
      if (creator_id)
        creator = new CriticUser(creator_id);
      else
        return null;
    return creator;
  }

  Object.defineProperties(this, { user: { get: getUser, enumerable: true },
                                  creator: { get: getCreator, enumerable: true }});
  Object.freeze(this);
}

function CriticReviewRebase(review, user_id, old_head_id, new_head_id, new_upstream_id, branch_name)
{
  this.review = review;
  this.user = new CriticUser(user_id);
  this.oldHead = review.repository.getCommit(old_head_id);
  this.newHead = review.repository.getCommit(new_head_id);
  this.newUpstream = new_upstream_id && review.repository.getCommit(new_upstream_id);
  this.branchName = branch_name;

  Object.freeze(this);
}

function CriticReviewCreated(review_id)
{
  this.id = review_id;
}

function CriticTrackedBranch(review, remote, name, disabled)
{
  this.review = review;
  this.remote = remote;
  this.name = name;
  this.disabled = disabled;

  Object.freeze(this);
}

function CriticReview(arg)
{
  var review_id, created;

  if (arg && typeof arg == "object" && arg instanceof CriticReviewCreated)
  {
    review_id = arg.id;
    created = true;
  }
  else
  {
    review_id = ~~arg;
    created = false;
  }

  var result = db.execute("SELECT branch, state, closed_by, dropped_by, summary, description FROM reviews WHERE id=%d", review_id)[0];

  if (!result)
    throw CriticError(format("%d: invalid review ID", review_id));

  this.id = review_id;
  this.owners = [];
  this.state = result.state;
  this.closedBy = result.closed_by && new CriticUser(result.closed_by);
  this.droppedBy = result.dropped_by && new CriticUser(result.dropped_by);
  this.summary = result.summary || "";
  this.description = result.description || "";

  var owners = db.execute("SELECT uid FROM reviewusers WHERE review=%d AND owner", review_id);
  for (var index = 0; index < owners.length; ++index)
    this.owners.push(new CriticUser(owners[index].uid));

  var self = this;
  var commits = null;
  var branch = null, branch_id = result.branch;
  var repository = null;
  var comment_chains = null;
  var users = null;
  var reviewers = null;
  var watchers = null;
  var progress = null;
  var batches = null;
  var filters = null;
  var rebases = null;
  var trackedBranch;

  var internal = review_internals[review_id] = {};
  internal.filters = filters;
  internal.created = created;

  result = null;
  owners = null;

  function getCommits()
  {
    if (!commits)
    {
      var all = [];
      var repository = getRepository();

      var result = db.execute("SELECT DISTINCT child FROM changesets JOIN reviewchangesets ON (changeset=id) WHERE review=%d", self.id);

      for (var index = 0; index < result.length; ++index)
        all.push(repository.getCommit(result[index].child));

      commits = new CriticCommitSet(all);
    }

    return commits;
  }

  function getBranch()
  {
    if (!branch)
      branch = new CriticBranch({ id: branch_id, repository: repository, review: self });

    return branch;
  }

  function getRepository()
  {
    if (!repository)
      if (branch)
        repository = branch.repository;
      else
      {
        var result = db.execute("SELECT repository FROM branches WHERE id=%d", branch_id)[0];
        repository = new CriticRepository(result.repository);
      }

    return repository;
  }

  function getCommentChains()
  {
    if (!comment_chains)
    {
      comment_chains = [];
      comment_chains.issues = [];
      comment_chains.notes = [];

      var result = db.execute("SELECT id, review, batch, uid, time, type, state, origin, file, first_commit, last_commit, closed_by, addressed_by FROM commentchains WHERE review=%d AND state NOT IN ('draft', 'empty') ORDER BY time ASC", review_id);

      for (var index = 0; index < result.length; ++index)
      {
        var chain = new CriticCommentChain(result[index], { review: self });
        comment_chains.push(chain);
        if (chain.type == CriticCommentChain.TYPE_ISSUE)
          comment_chains.issues.push(chain);
        else
          comment_chains.notes.push(chain);
      }

      Object.freeze(comment_chains.issues);
      Object.freeze(comment_chains.notes);
      Object.freeze(comment_chains);
    }

    return comment_chains;
  }

  function getUsers()
  {
    if (!users)
    {
      users = [];
      users.type = {};

      var result = db.execute("SELECT uid, type FROM reviewusers WHERE review=%d", self.id);

      for (var index = 0; index < result.length; ++index)
      {
        var user = new CriticUser(result[index].uid);

        users.push(user);
        users.type[user.id] = result[index].type;
      }

      Object.freeze(users.type);
      Object.freeze(users);
    }

    return users;
  }

  function getReviewers()
  {
    if (!reviewers)
    {
      reviewers = {};

      var result = db.execute("SELECT DISTINCT assignee FROM fullreviewuserfiles WHERE review=%d", self.id);

      for (var index = 0; index < result.length; ++index)
      {
        var user = new CriticUser(result[index].assignee);

        reviewers[user.id] = user;
        reviewers[user.name] = user;
      }

      Object.freeze(reviewers);
    }

    return reviewers;
  }

  function getWatchers()
  {
    if (!watchers)
    {
      watchers = {};

      var result = db.execute("SELECT reviewusers.uid FROM reviewusers LEFT OUTER JOIN fullreviewuserfiles ON (reviewusers.review=fullreviewuserfiles.review AND reviewusers.uid=fullreviewuserfiles.assignee) WHERE reviewusers.review=%d AND fullreviewuserfiles.assignee IS NULL", self.id);

      for (var index = 0; index < result.length; ++index)
      {
        var user = new CriticUser(result[index].uid);

        watchers[user.id] = user;
        watchers[user.name] = user;
      }

      Object.freeze(watchers);
    }

    return watchers;
  }

  function getBatches()
  {
    if (!batches)
    {
      batches = [];

      var result = db.execute("SELECT id FROM batches WHERE review=%d ORDER BY id ASC", self.id);

      for (var index = 0; index < result.length; ++index)
        batches.push(new CriticBatch({ id: result[index].id, review: self }));

      Object.freeze(batches);
    }

    return batches;
  }

  function getFilters()
  {
    if (!filters)
    {
      filters = [];

      var result = db.execute("SELECT uid, path, type, creator FROM reviewfilters WHERE review=%d", self.id);

      for (var index = 0; index < result.length; ++index)
      {
        var row = result[index];
        filters.push(new CriticReviewFilter(self, row.uid, row.path, row.type, row.creator));
      }

      Object.freeze(filters);
    }

    return filters;
  }

  function getRebases()
  {
    if (!rebases)
    {
      rebases = [];

      var result = db.execute("SELECT id, uid, old_head, new_head, new_upstream, branch FROM reviewrebases WHERE review=%d AND new_head IS NOT NULL ORDER BY id DESC", self.id);

      for (var index = 0; index < result.length; ++index)
      {
        var row = result[index];
        rebases.push(new CriticReviewRebase(self, row.uid, row.old_head, row.new_head, row.new_upstream, row.branch));
      }

      Object.freeze(rebases);
    }

    return rebases;
  }

  function getProgress()
  {
    if (!progress)
    {
      var pending_lines = 0;
      var pending_files = 0;
      var reviewed_lines = 0;
      var reviewed_files = 0;
      var issues;

      var result = db.execute("SELECT state, SUM(deleted) + SUM(inserted) AS count FROM reviewfiles WHERE review=%d GROUP BY state", self.id);
      for (var index = 0; index < result.length; ++index)
        if (result[index].state == "pending")
          pending_lines = result[index].count;
        else
          reviewed_lines = result[index].count;

      var result = db.execute("SELECT state, COUNT(*) AS count FROM reviewfiles WHERE review=%d GROUP BY state", self.id);
      for (var index = 0; index < result.length; ++index)
        if (result[index].state == "pending")
          pending_files = result[index].count;
        else
          reviewed_files = result[index].count;

      result = null;
      issues = db.execute("SELECT COUNT(id) AS count FROM commentchains WHERE review=%d AND type='issue' AND state='open'", self.id)[0].count;

      progress = { accepted: self.state == "open" && pending_files == 0 && issues == 0,
                   finished: self.state == "closed",
                   dropped: self.state == "dropped",
                   pendingLines: pending_lines,
                   pendingFiles: pending_files,
                   reviewedLines: reviewed_lines,
                   reviewedFiles: reviewed_files,
                   openIssues: issues,
                   toString: function ()
                     {
                       if (this.finished)
                         return "Finished!";
                       else if (this.accepted)
                         return "Accepted!";
                       else if (this.dropped)
                         return "Dropped...";

                       var percent, pending = this.pendingLines, reviewed = this.reviewedLines;

                       if (pending_lines == 0 && reviewed_lines == 0)
                         percent = "?? %";
                       else
                       {
                         var percent_exact = 100 * reviewed / (pending + reviewed);
                         var percent_rounded = Math.round(percent_exact);

                         if (percent_exact == 100)
                           percent = "100 %";
                         else if (reviewed == 0)
                           percent = "No progress";
                         else if (percent_rounded > 0 && percent_rounded < 100)
                           percent = format("%d %%", percent_rounded);
                         else
                         {
                           for (var precision = 1; precision < 10; ++precision)
                           {
                             percent = format(format("%%.%df", precision), percent_exact);
                             if (percent.charAt(percent.length - 1) != '0')
                               break;
                           }
                           percent += " %";
                         }
                       }

                       if (this.openIssues)
                         return format("%s and %d issue%s", percent, this.openIssues, this.openIssues > 1 ? "s" : "");
                       else
                         return percent;
                     }};

      Object.freeze(progress);
    }

    return progress;
  }

  function getTrackedBranch()
  {
    if (trackedBranch === void 0)
    {
      var result = db.execute("SELECT remote, remote_name, disabled FROM trackedbranches WHERE repository=%d AND local_name=%s",
                              self.repository.id, self.branch.name)[0];

      if (result)
        trackedBranch = new CriticTrackedBranch(self, result.remote, result.remote_name, result.disabled);
      else
        trackedBranch = null;
    }

    return trackedBranch;
  }

  Object.defineProperties(this, { commits: { get: getCommits, enumerable: true },
                                  branch: { get: getBranch, enumerable: true },
                                  repository: { get: getRepository, enumerable: true },
                                  commentChains: { get: getCommentChains, enumerable: true },
                                  users: { get: getUsers, enumerable: true },
                                  reviewers: { get: getReviewers, enumerable: true },
                                  watchers: { get: getWatchers, enumerable: true },
                                  batches: { get: getBatches, enumerable: true },
                                  filters: { get: getFilters, enumerable: true },
                                  rebases: { get: getRebases, enumerable: true },
                                  progress: { get: getProgress, enumerable: true },
                                  trackedBranch: { get: getTrackedBranch, enumerable: true }});
  Object.freeze(this);
}

CriticReview.prototype.getBatch = function (id)
  {
    return new CriticBatch({ id: Number(id) });
  };

CriticReview.prototype.getCommentChain = function (id)
  {
    return new CriticCommentChain(id, { review: this });
  };

CriticReview.prototype.getComment = function (id)
  {
    id = ~~id;

    var result = db.execute("SELECT chain, batch, uid, time, state, comment FROM comments WHERE id=%d AND state='current'", id)[0];
    var chain = new CriticCommentChain(result.chain, { review: this });

    return new CriticComment(chain.id, result.batch, id, result.uid, result.time, result.state, result.comment, { chain: chain });
  };

CriticReview.prototype.getChangeset = function (commit)
  {
    if (commit.parents.length > 1)
    {
      var result = db.execute("SELECT id FROM changesets WHERE child=%d AND type='merge'", commit.id);
      var changesets = [];

      for (var index = 0; index < result.length; ++index)
        changesets.push(new CriticChangeset(this.repository, { id: result[index].id, child: commit, review: this }));

      return new CriticMergeChangeset(changesets);
    }
    else
    {
      var result = db.execute("SELECT id FROM changesets WHERE child=%d AND type='direct'", commit.id)[0];
      return new CriticChangeset(this.repository, { id: result.id, parent: commit.parents[0], child: commit, review: this });
    }
  };

CriticReview.prototype.startBatch = function (user)
  {
    user = user || global.user;

    if (!(user instanceof CriticUser))
      throw CriticError("invalid argument; expected user object");

    return new CriticBatch({ internals: batch_internals, review: this, user: user, review_created: CriticReview_isCreated(this) });
  };

CriticReview.prototype.generateSubjectLine = function (user, preference)
  {
    var data = { id: format("r/%s", this.id), summary: this.summary, progress: String(this.progress), branch: this.branch.name };
    var user_format = user.getPreference(preference);

    try
    {
      return format(user_format, data);
    }
    catch (e)
    {
      var default_format = db.execute("SELECT default_string FROM preferences WHERE item=%s", preference);
      return format(default_format, data);
    }
  };

CriticReview.prototype.getReviewableCommits = function (user)
  {
    user = user || global.user;

    if (!(user instanceof CriticUser))
      throw CriticError("invalid argument; expected user object");

    var result = db.execute("SELECT DISTINCT child FROM changesets JOIN fullreviewuserfiles ON (changeset=id) WHERE review=%d AND assignee=%d", this.id, user.id);

    var commits = [];

    for (var index = 0; index < result.length; ++index)
      commits.push(this.repository.getCommit(result[index].child));

    return new CriticCommitSet(commits);
  };

CriticReview.prototype.getFullChangeset = function ()
  {
    return this.branch.commits.getChangeset({ review: this });
  };

CriticReview.prototype.getReviewableChangeset = function (user)
  {
    var commits = this.getReviewableCommits(user);

    if (commits.heads.length > 1 && commits.upstreams.length == 1)
      commits = this.commits.restrict(commits.heads, commits.upstreams);

    return commits.getChangeset({ review: this });
  };

CriticReview.prototype.increaseSerial = function ()
  {
    db.rollback();
    db.execute("UPDATE reviews SET serial=serial+1 WHERE id=%d", this.id);
    db.commit();
  };

function CriticPartition(review, commits, rebase)
{
  this.review = review;
  this.commits = commits;
  this.rebase = rebase;

  Object.freeze(this);
}

CriticReview.prototype.getCommitPartitions = function ()
  {
    var rebases = this.rebases;

    if (rebases.length == 0)
      return new CriticPartition(this, this.commits, null);

    var partition_commits = this.commits.restrict([this.branch.head]);
    var remaining_commits = this.commits.without(partition_commits);
    var partitions = [];

    for (var index = rebases.length - 1; index >= 0; --index)
    {
      var rebase = rebases[index];

      partitions.push(new CriticPartition(this, partition_commits, rebase));

      partition_commits = remaining_commits.restrict([rebase.oldHead]);
      if (partition_commits.length != 0)
        remaining_commits = remaining_commits.without(partition_commits);
    }

    partitions.push(new CriticPartition(this, partition_commits, null));

    return Object.freeze(partitions);
  };

CriticReview.prototype.prepareRebase = function (data)
  {
    db.rollback();

    if (db.execute("SELECT 1 FROM reviewrebases WHERE review=%d AND new_head IS NULL", this.id).length != 0)
      throw CriticError("review rebase already in progress");

    var user = data.user || global.user;

    if (!!data.historyRewrite + !!data.singleCommit + !!data.newUpstream != 1)
      throw CriticError("invalid argument; exactly one of data.historyRewrite, data.singleCommit and data.newUpstream must be specified");

    var old_head_id = this.branch.head.id;

    if (data.historyRewrite)
      db.execute("INSERT INTO reviewrebases (review, old_head, uid) VALUES (%d, %d, %d)",
                 this.id, old_head_id, user.id);
    else
    {
      var upstreams = this.branch.commits.upstreams;

      if (upstreams.length > 1)
        throw CriticError("rebase not supported; review has multiple upstreams");

      var branch = data.branch || null;
      var old_upstream = upstreams[0];

      if (data.singleCommit)
        db.execute("INSERT INTO reviewrebases (review, old_head, old_upstream, uid, branch) VALUES (%d, %d, %d, %d, %s)",
                   this.id, old_head_id, old_upstream.id, user.id, branch);
      else
        db.execute("INSERT INTO reviewrebases (review, old_head, old_upstream, new_upstream, uid, branch) VALUES (%d, %d, %d, %d, %d, %s)",
                   this.id, old_head_id, old_upstream.id, data.newUpstream.id, user.id, branch);
    }

    db.commit();
  };

CriticReview.prototype.cancelRebase = function (data)
  {
    var result = db.execute("SELECT id FROM reviewrebases WHERE review=%d AND new_head IS NULL", this.id)[0];

    if (!result)
      throw CriticError("no review rebase in progress");

    db.execute("DELETE FROM reviewrebases WHERE id=%d", result.id);
    db.commit();
  };

CriticReview.prototype.close = function (user)
  {
    if (this.state != "open")
      throw CriticError("review is not open");
    if (!this.progress.accepted)
      throw CriticError("review is not accepted");

    user = user || global.user;

    if (!(user instanceof CriticUser))
      throw CriticError("invalid argument; expected user object");

    db.execute("UPDATE reviews SET state='closed', closed_by=%d, serial=serial+1 WHERE id=%d", user.id, this.id);
    db.commit();
  };

CriticReview.create = function (data)
  {
    if (!("upstream" in data))
      throw CriticError("missing argument: upstream");
    if (!("summary" in data))
      throw CriticError("missing argument: summary");
    if (!("branch" in data))
      throw CriticError("missing argument: branch");
    if (!("owner" in data))
      throw CriticError("missing argument: owner");

    var upstream = data.upstream;
    var summary = String(data.summary);
    var description = data.description || null;
    var branch = String(data.branch);
    var owner = data.owner;

    if (!(upstream instanceof CriticCommit))
      throw CriticError("invalid argument: upstream");
    if (branch.substring(0, 2) != "r/")
      throw CriticError("invalid argument: branch (doesn't have 'r/' prefix)");
    if (!(owner instanceof CriticUser))
      throw CriticError("invalid argument: owner");

    var repository = data.repository;

    try
    {
      repository.revparse(branch);
      branch = false;
    }
    catch (exception)
    {
    }

    if (!branch)
      throw CriticError("invalid argument: branch (already exists)");

    repository.run("branch", branch, upstream.sha1);

    var branch_id = db.execute("INSERT INTO branches (name, head, base, tail, repository) VALUES (%s, %d, %d, %d, %d) RETURNING id",
                               branch, upstream.id, repository.branch.id, upstream.id, repository.id)[0].id;

    var review_id = db.execute("INSERT INTO reviews (type, branch, state, summary, description) VALUES (%s, %d, %s, %s, %s) RETURNING id",
                               "official", branch_id, "open", summary, description)[0].id;

    db.execute("INSERT INTO reviewusers (review, uid, owner) VALUES (%d, %d, TRUE)", review_id, owner.id);

    return new CriticReview(review_id);
  };

CriticReview.find = function (data)
  {
    var result;

    if (data.repositoryURL && data.branchName)
    {
      if (data.repositoryURL.substring(0, hostname.length + 1) == hostname + ":")
        result = db.execute("SELECT reviews.id " +
                            "  FROM reviews " +
                            "  JOIN branches ON (branches.id=reviews.branch) " +
                            "  JOIN repositories ON (repositories.id=branches.repository) " +
                            " WHERE branches.name=%s " +
                            "   AND repositories.path=%s",
                            data.branchName,
                            data.repositoryURL.substring(hostname.length + 1));
      else
        result = db.execute("SELECT reviews.id " +
                            "  FROM reviews " +
                            "  JOIN branches ON (branches.id=reviews.branch) " +
                            "  JOIN trackedbranches ON (trackedbranches.repository=branches.repository " +
                            "                       AND trackedbranches.local_name=branches.name) " +
                            " WHERE trackedbranches.remote_name=%s " +
                            "   AND trackedbranches.remote=%s",
                            data.branchName,
                            data.repositoryURL);
    }

    return scoped(
      result,
      function ()
      {
        return this.apply(
          function (review_id)
          {
            return new CriticReview(review_id);
          });
      });
  };

CriticReview.list = function (data)
  {
    data = data || {};

    var tables = ["reviews"];
    var conditions = ["TRUE"];
    var argv = [];

    if (data.repository)
    {
      var repository_id, repository_name;

      if (data.repository instanceof CriticRepository)
        repository_id = data.repository.id;
      else if (parseInt(data.repository) === data.repository)
        repository_id = data.repository;
      else
        repository_name = String(data.repository);

      tables.push("branches ON (branches.id=reviews.branch)");

      if (repository_id !== void 0)
      {
        conditions.push("branches.repository=%d");
        argv.push(repository_id);
      }
      else
      {
        tables.push("repositories ON (repositories.id=branches.repository)");
        conditions.push("repositories.name=%s");
        argv.push(repository_name);
      }
    }

    if (data.state)
    {
      var valid_states = { open: true, closed: true, dropped: true };

      if (!(data.state in valid_states))
        throw CriticError(format("invalid argument: data.state=%r not valid", String(data.state)));

      conditions.push("reviews.state=%s");
      argv.push(data.state);
    }

    if (data.owner)
    {
      var owner_id, owner_name;

      if (data.owner instanceof CriticUser)
        owner_id = data.owner.id;
      else if (parseInt(data.owner) === data.owner)
        owner_id = data.owner;
      else
        owner_name = String(data.owner);

      tables.push("reviewusers ON (reviewusers.review=reviews.id)");
      conditions.push("reviewusers.owner");

      if (owner_id !== void 0)
      {
        conditions.push("reviewusers.uid=%d");
        argv.push(owner_id);
      }
      else
      {
        tables.push("users ON (users.id=reviewusers.uid)");
        conditions.push("users.name=%s");
        argv.push(owner_name);
      }
    }

    var query = format(
      "SELECT reviews.id FROM %(tables)s WHERE %(conditions)s ORDER BY reviews.id",
      { tables: tables.join(" JOIN "),
        conditions: conditions.join(" AND ") });

    return scoped(
      db.execute.bind(db, query).apply(null, argv),
      function ()
      {
        return this.apply(
          function (review_id)
          {
            return new CriticReview(review_id);
          });
      });
  };
