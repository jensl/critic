/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2014 Jens Lindström, Opera Software ASA

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

function signalBranchTracker()
{
  if (branchtracker_pid_path)
  {
    var pid = parseInt(IO.File.read(branchtracker_pid_path));
    var SIGHUP = 1;

    OS.Process.kill(pid, SIGHUP);
  }
}

function CriticTrackedBranch(id, data) {
  data = data || {};

  var self = this;
  var branch_id, branch = data.branch || void 0;
  var review_id, review = data.review || void 0;
  var remote_name, disabled, pending;

  this.id = id;

  scoped(
    db.execute(("SELECT branches.id, remote, remote_name, disabled, updating," +
                "       next IS NULL AS pending" +
                "  FROM trackedbranches" +
                "  JOIN branches ON (branches.repository=trackedbranches.repository" +
                "                AND branches.name=trackedbranches.local_name)" +
                " WHERE trackedbranches.id=%d"),
               id),
    function () {
      var row = this[0];

      if (!row)
        throw CriticError(format("invalid tracked branch id: %d", id));

      branch_id = row.id;
      remote_name = row.remote_name;
      disabled = row.disabled;
      pending = row.pending;

      self.remote = row.remote;
      self.forced = row.forced;
      self.updating = row.updating;
    });

  if (!review) {
    scoped(
      db.execute(("SELECT id" +
                  "  FROM reviews" +
                  " WHERE branch=%d"),
                 branch_id),
      function () {
        var row = this[0];

        if (row)
          review_id = row.id;
      });
  }

  function getRemoteName() {
    return remote_name;
  }

  function getDisabled() {
    return disabled;
  }

  function getPending() {
    return pending;
  }

  function getBranch() {
    if (branch === void 0)
      branch = new CriticBranch({ id: branch_id });
    return branch;
  }

  function getReview() {
    if (review === void 0) {
      if (review_id !== void 0)
        review = new CriticReview(review_id);
      else
        review = null;
    }
    return review;
  }

  this.enable = function (new_name) {
    disabled = false;

    if (new_name)
      remote_name = new_name;
    else
      new_name = remote_name;

    db.execute(("UPDATE trackedbranches" +
                "   SET remote_name=%s" +
                "       disabled=FALSE" +
                " WHERE id=%d"),
               new_name, this.id);

    this.triggerUpdate();
  };

  this.disable = function () {
    disabled = true;

    db.execute(("UPDATE trackedbranches" +
                "   SET disabled=TRUE" +
                " WHERE id=%d"),
               this.id);
    db.commit();
  };

  this.triggerUpdate = function () {
    pending = true;

    db.execute(("UPDATE trackedbranches" +
                "   SET next=NULL" +
                " WHERE id=%d"),
               this.id);
    db.commit();

    signalBranchTracker();
  };

  Object.defineProperties(this, { name: { get: getRemoteName,
                                          enumerable: true },
                                  disabled: { get: getDisabled,
                                              enumerable: true },
                                  pending: { get: getPending,
                                             enumerable: true },
                                  branch: { get: getBranch,
                                            enumerable: true },
                                  review: { get: getReview,
                                            enumerable: true } });
  Object.freeze(this);
}

CriticTrackedBranch.prototype.getLogEntry = function (value) {
  if (value === void 0)
    value = this.branch.head.sha1;

  var result = db.execute(("  SELECT time, from_sha1, to_sha1, hook_output, " +
                           "         successful" +
                           "    FROM trackedbranchlog" +
                           "   WHERE branch=%d" +
                           "     AND to_sha1=%s" +
                           "ORDER BY time DESC" +
                           "   LIMIT 1"),
                          this.id, value);
  var row = result[0];

  if (!row)
    return null;

  var from_commit = null, to_commit = null;

  if (row.from_sha1 && !/0{40}/.test(row.from_sha1))
    from_commit = this.branch.repository.getCommit(row.from_sha1);
  if (row.to_sha1 && !/0{40}/.test(row.to_sha1))
    to_commit = this.branch.repository.getCommit(row.to_sha1);

  return Object.freeze({ time: row.time,
                         oldValue: from_commit,
                         newValue: to_commit,
                         hookOutput: row.hook_output,
                         successful: row.successful });
};

CriticTrackedBranch.find = function (data) {
  var result;

  if (data.branch) {
    result = db.execute(("SELECT id" +
                         "  FROM trackedbranches" +
                         " WHERE repository=%d" +
                         "   AND local_name=%s"),
                        data.branch.repository.id, data.branch.name);
  } else if (data.remote && data.name) {
    result = db.execute(("SELECT id" +
                         "  FROM trackedbranches" +
                         " WHERE remote=%s" +
                         "   AND remote_name=%s"),
                        data.remote, data.name);
  } else {
    throw CriticError("invalid input");
  }

  var row = result[0];

  if (row)
    return new CriticTrackedBranch(row.id, data);
  else
    return null;
};
