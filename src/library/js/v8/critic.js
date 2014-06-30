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

Date.prototype.format = function ()
  {
    return format("%04d-%02d-%02d %02d:%02d", this.getFullYear(), this.getMonth() + 1, this.getDate(), this.getHours(), this.getMinutes());
  };

Date.prototype.toSQLTimestamp = function ()
  {
    return format("%04d-%02d-%02d %02d:%02d:%02d", this.getFullYear(), this.getMonth() + 1, this.getDate(), this.getHours(), this.getMinutes(), this.getSeconds());
  };

function CriticError(message, exception)
{
  if (!this)
    return new CriticError(message, exception);

  this.name = "CriticError";
  this.message = message;

  if (exception)
  {
    this.message += " (" + exception.message + ")";
    this.stack = exception.stack;
  }
  else
  {
    try
    {
      /* Trigger a native exception to copy a stack trace from. */
      "foo"();
    }
    catch (exception)
    {
      this.stack = exception.stack.replace(/^([^\n]+\n){2}/, "");
    }
  }
}

CriticError.prototype = Object.create(Error.prototype);

if (!String.prototype.startsWith)
{
  String.prototype.startsWith = function (prefix)
    {
      return this.length >= prefix.length && this.substring(0, prefix.length) == prefix;
    };
}

Error.prepareStackTrace = function (error, callsites)
  {
    /* Calling methods on CallSite objects sometimes throws an exception saying
       "illegal access."  Unknown whether this is a bug in V8 or in v8-jsshell,
       but the latter seems more likely.  This has in particular been observed
       when calling the "isConstructor" method. */
    function checked(obj, name)
    {
      try
      {
        return obj[name]();
      }
      catch (error)
      {
        return format("<%s: %s>", name, String(error));
      }
    }

    function describeCallSite(callsite)
    {
      if (!callsite || typeof callsite == "string")
        return "<unknown call-site>";
      if (callsite.isEval())
        return format("eval at %s", describeCallSite(callsite.getEvalOrigin()));

      var filename = checked(callsite, "getFileName");
      var where;

      if (filename)
      {
        if (filename.startsWith(library_path + "/"))
          filename = "<Library>/" + filename.substring(library_path.length + 1);
        else
          filename = "<Extension>/" + filename;

        where = format("at %s:%d", filename, checked(callsite, "getLineNumber"));
      }
      else if (checked(callsite, "isNative"))
        where = "in native code";
      else
        where = "at unknown location";

      var fn = checked(callsite, "getFunction");
      var fnname = checked(callsite, "getFunctionName");
      var what;

      if (fnname)
      {
        if (checked(callsite, "isConstructor") === true)
          what = format("new %s()", fnname);
        else
          what = format("%s()", fnname);
      }
      /* Oddly enough, top-level program code also has a function, whose
         .toString() returns "function <program source>". */
      else if (fn && String(fn).startsWith("function ("))
        what = "<unnamed function>";
      else
        what = "<program code>";

      return format("%s %s", what, where);
    }

    return callsites.map(describeCallSite).join("\n");
  };

var configuration = {
  maxCommits: 1024
};

Module.load("critic-user.js");
Module.load("critic-file.js");
Module.load("critic-git.js");
Module.load("critic-commitset.js");
Module.load("critic-changeset.js");
Module.load("critic-branch.js");
Module.load("critic-dashboard.js");
Module.load("critic-review.js");
Module.load("critic-comment.js");
Module.load("critic-batch.js");
Module.load("critic-filters.js");
Module.load("critic-mail.js");
Module.load("critic-text.js");
Module.load("critic-html.js");
Module.load("critic-storage.js");
Module.load("critic-log.js");
Module.load("critic-statistics.js");
Module.load("critic-trackedbranch.js");
Module.load("critic-cli.js");

Module.assign("CriticError", CriticError);
Module.assign("Error", CriticError);

Module.assign("User", CriticUser);
Module.assign("AnonymousUser", CriticAnonymousUser);
Module.assign("File", CriticFile.find);
Module.assign("Repository", CriticRepository);
Module.assign("Branch", CriticBranch);
Module.assign("Dashboard", CriticDashboard);
Module.assign("Review", CriticReview);
Module.assign("OldBatch", CriticBatch);
Module.assign("CommentChain", CriticCommentChain);
Module.assign("CommitSet", CriticCommitSet);
Module.assign("Filters", CriticFilters);
Module.assign("Statistics", CriticStatistics);
Module.assign("Storage", CriticStorage);
Module.assign("MailTransaction", CriticMailTransaction);
Module.assign("TrackedBranch", CriticTrackedBranch);
Module.assign("Log", CriticLog);
Module.assign("html", CriticHtml);
Module.assign("text", Object.freeze({ reflow: reflow }));

var extras_dir = format("%s/extras", Module.path);
var extra_modules = [];

if (IO.File.isDirectory(extras_dir))
{
  IO.File.listDirectory(extras_dir).forEach(
    function (module_name)
    {
      var module_dir = format("%s/%s", extras_dir, module_name);
      var module_main_js = format("%s/main.js", module_dir);
      if (IO.File.isDirectory(module_dir) &&
          IO.File.isRegularFile(module_main_js))
      {
        var module = new Module();
        module.load(module_main_js);
        if (typeof module.name == "string")
          module_name = module.name;
        Module.assign(module_name, module);
        extra_modules.push(module);
      }
    });
}

Module.assign("Changeset", Object.freeze(Object.defineProperty(function () {}, "prototype", { value: CriticChangeset.prototype })));
Module.assign("MergeChangeset", Object.freeze(Object.defineProperty(function () {}, "prototype", { value: CriticMergeChangeset.prototype })));
Module.assign("ChangesetLine", Object.freeze(CriticChangesetLineConstants));

Module.assign("printProfilingData", function () {});

var global = {};
var db = null, dbparams = null;

var library_path;
var hostname;
var extension_id;
var user_id;
var role;
var git_executable;
var python_executable;
var python_path;
var repository_work_copy_path;
var changeset_address;
var branchtracker_pid_path;
var maildelivery_pid_path;
var is_development;

function setup(data)
{
  if (!db)
  {
    var dbparams = {};

    if (data.dbname)
      dbparams.dbname = data.dbname;
    if (data.dbuser)
      dbparams.user = data.dbuser;
    if (data.dbpass)
      dbparams.password = data.dbpass;

    db = new PostgreSQL.Connection(dbparams);
  }

  if (data.user_id)
  {
    global.user = new CriticUser(data.user_id);
    if (data.extension_id)
    {
      Module.assign("storage", global.storage = new CriticStorage(global.user));
      Module.assign("log", global.log = new CriticLog(global.user));
    }
  }
  else
  {
    global.user = new CriticAnonymousUser();
  }

  library_path = IO.Path.dirname(data.criticjs_path);
  hostname = data.hostname;
  extension_id = data.extension_id;
  user_id = data.user_id;
  role = data.role;
  git_executable = data.git;
  python_executable = data.python;
  python_path = data.python_path;
  repository_work_copy_path = data.repository_work_copy_path;
  changeset_address = data.changeset_address;
  branchtracker_pid_path = data.branchtracker_pid_path;
  maildelivery_pid_path = data.maildelivery_pid_path;
  is_development = data.is_development;

  IO.File.chdir(data.extension_path);

  var pagesize = parseInt((new OS.Process("getconf PAGESIZE", { shell: true })).call());

  if (data.rlimit.cpu)
    OS.Process.setrlimit("cpu", data.rlimit.cpu);
  if (data.rlimit.rss)
    OS.Process.setrlimit("rss", data.rlimit.rss * (1024 * 1024) / pagesize);

  var critic = this;

  extra_modules.forEach(
    function (module)
    {
      if (typeof module.global.setup == "function")
        module.global.setup(critic, data);
      module.close();
    });
}

function shutdown()
{
  if (db)
    db.close();

  for (var index = 0; index < all_repositories.length; ++index)
    all_repositories[index].shutdown();
}

function connect(data)
{
  dbparams = {};

  if (data.dbname)
    dbparams.dbname = data.dbname;
  if (data.dbuser)
    dbparams.user = data.dbuser;
  if (data.dbpass)
    dbparams.password = data.dbpass;

  db = new PostgreSQL.Connection(dbparams);
}

function reconnect()
{
  db.reset();
  db = new PostgreSQL.Connection(dbparams);
}

Module.assign("setup", setup);
Module.assign("shutdown", shutdown);
Module.assign("connect", connect);
Module.assign("reconnect", reconnect);
