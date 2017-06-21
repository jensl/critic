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

function CriticBranch(options)
{
  var repository, branch_id, name, result;

  if ("id" in options)
  {
    branch_id = options.id;

    result = db.execute("SELECT repository, name, head, base FROM branches WHERE id=%d", branch_id)[0];

    if (!result)
      throw CriticError(format("%d: invalid branch ID", branch_id));

    repository = options.repository || new CriticRepository(result.repository);
    name = result.name;
  }
  else if ("repository" in options && "name" in options)
  {
    repository = options.repository;
    name = options.name;

    result = db.execute("SELECT id, head, base FROM branches WHERE repository=%d AND name=%s", repository.id, name)[0];

    if (!result)
      throw CriticError(format("%s: no such branch", name));

    branch_id = result.id;
  }
  else
    throw CriticError("invalid argument; must specify either 'id' or 'repository'+'name'");

  var self = this;
  var head_id = result.head, head = options.head || null;
  var base_id = result.base, base = options.base || null;
  var review = options.review || void 0;
  var commits;

  result = null;

  function getHead()
  {
    if (!head)
      head = self.repository.getCommit(head_id);

    return head;
  }

  function getBase()
  {
    if (!base)
      if (!base_id)
        return null;
      else
        base = new CriticBranch({ id: base_id, repository: self.repository });

    return base;
  }

  function getReview()
  {
    if (review === void 0)
    {
      var result = db.execute("SELECT id FROM reviews WHERE branch=%d", self.id)[0];

      if (result)
        review = new CriticReview(result.id);
      else
        review = null;
    }

    return review;
  }

  function getCommits()
  {
    if (!commits)
    {
      var result = db.execute("SELECT commit FROM branchcommits WHERE branch=%d LIMIT %d", branch_id, configuration.maxCommits + 1);

      if (result.length > configuration.maxCommits)
        throw CriticError(format("implementation limit; branch contains more than %d commits", configuration.maxCommits));

      var all_commits = [];

      for (var index = 0; index < result.length; ++index)
        all_commits.push(repository.getCommit(result[index].commit));

      commits = new CriticCommitSet(all_commits);
    }

    return commits;
  }

  this.repository = repository;
  this.id = branch_id;
  this.name = name;

  Object.defineProperties(this, { head: { get: getHead, enumerable: true },
                                  base: { get: getBase, enumerable: true },
                                  review: { get: getReview, enumerable: true },
                                  commits: { get: getCommits, enumerable: true }});
  Object.freeze(this);
}

Object.defineProperties(CriticBranch.prototype, {

  getWorkCopy: { writable: true, value: function ()
    {
      return new CriticRepositoryWorkCopy(this.repository, this.name);
    } },

  getCheckBranch: { writable: true, value: function (upstream)
    {
      return new CriticCheckBranch(this, upstream);
    } }

});

function CriticCheckBranch(branch, upstream)
{
  this.branch = branch;
  this.upstream = upstream;
}

Object.defineProperties(CriticCheckBranch.prototype, {

  addNote: {
    writable: true,
    value: function (commit, data)
    {
      var sha1, review_id, note, user;

      if (commit instanceof CriticCommit)
        sha1 = commit.sha1;
      else
        throw CriticError("invalid commit argument; expected critic.Commit object");

      if (data.review)
      {
        if (data.review instanceof CriticReview)
          review_id = data.review.id;
        else
          throw CriticError("invalid data.review argument; expected critic.Review object");
      }
      else
        review_id = null;

      if (data.note)
        note = String(note);
      else
        note = null;

      if (data.user)
        user = data.user;
      else
        user = global.user;

      db.execute("INSERT INTO checkbranchnotes (repository, branch, upstream, sha1, uid, review, text) VALUES (%d, %s, %s, %s, %d, %d, %s)",
                 this.branch.repository.id, this.branch.name, this.upstream, sha1, user.id, review_id, note);
    }
  }

});
