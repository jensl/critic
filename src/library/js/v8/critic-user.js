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

function CriticFilter(user, repository, data)
{
  this.id = data.id;
  this.user = user;
  this.repository = repository;
  this.path = data.path;
  this.type = data.type;

  if (this.type == "reviewer")
    if (data.delegates)
    {
      this.delegates = data.delegates.split(/\s*,\s*|\s+/g).map(
        function (name)
        {
          return new CriticUser({ name: name });
        });
      Object.freeze(this.delegates);
    }
    else
      this.delegates = [];
  else
    this.delegates = null;

  Object.freeze(this);
}

function CriticUser(data)
{
  var user_id;

  if (typeof data == "number")
    user_id = data;
  else if (data.id)
    user_id = data.id;
  else
  {
    var result, name;

    if (typeof data == "string")
      name = data;

    if (name || data.name)
    {
      result = db.execute("SELECT id FROM users WHERE name=%s", name || data.name)[0];

      if (!result)
        throw CriticError(format("%s: no such user", name || data.name));
    }
    else
      throw CriticError("invalid argument; dictionary must specify one of id and name");

    user_id = result.id;
  }

  var result = db.execute("SELECT name, useremails.email, verified, fullname " +
                            "FROM users " +
                " LEFT OUTER JOIN useremails ON (useremails.id=users.email) " +
                           "WHERE users.id=%d",
                          user_id)[0];

  if (!result)
    throw CriticError(format("%d: invalid user ID", user_id));

  this.id = user_id;
  this.name = result.name;
  this.email = result.verified !== false ? result.email : null;
  this.fullname = result.fullname;
  this.isAnonymous = false;

  if (data.name && this.name != data.name)
    throw CriticError("invalid argument; name in dictionary doesn't match id in dictionary");

  result = null;

  Object.freeze(this);
}

Object.defineProperties(CriticUser.prototype, {
  toString: { value: function () { return format("%(fullname)s <%(email)s>", this); } },
  valueOf: { value: function () { return this.id; } },

  getPreference: {
    value: function (item)
      {
        var result = db.execute("SELECT type FROM preferences WHERE item=%s", item)[0];

        if (!result)
          throw CriticError(format("%s: no such preference", item));

        var value_column, value_filter = function (value) { return value; };

        switch (result.type)
        {
        case "boolean":
          value_filter = Boolean;

        case "number":
          value_column = "integer";
          break;

        case "string":
          value_column = "string";
        }

        var result = db.execute("  SELECT " + value_column + " AS value" +
                                "    FROM userpreferences" +
                                "   WHERE item=%s" +
                                "     AND (uid=%d OR uid IS NULL)" +
                                "     AND repository IS NULL" +
                                "     AND filter IS NULL " +
                                "ORDER BY uid NULLS LAST",
                                item, this.id)[0];

        return value_filter(result.value);
      }
  },

  isAuthor: {
    value: function (commit)
      {
        if (this.isAnonymous)
          return false;

        return this.email == commit.author.email;
      }
  },

  hasRole: {
    value: function (role)
      {
        if (this.isAnonymous)
          return false;

        return Boolean(db.execute("SELECT 1 FROM userroles WHERE uid=%d AND role=%s", this.id, role)[0]);
      }
  },

  getFilters: {
    value: function (repository)
      {
        if (this.isAnonymous)
          throw CriticError("not supported; user is anonymous");

        if (!(repository instanceof CriticRepository))
          throw CriticError("invalid argument: expected Repository object");

        var result = db.execute("SELECT id, " +
                                "       path, " +
                                "       type, " +
                                "       delegate AS delegates " +
                                "  FROM filters " +
                                " WHERE uid=%d " +
                                "   AND repository=%d",
                                this.id, repository.id);
        var filters = [];

        for (var index = 0; index < result.length; ++index)
          filters.push(new CriticFilter(this, repository, result[index]));

        Object.freeze(filters);

        return filters;
      }
  },

  addFilter: {
    value: function (repository, path, filter_type, delegates)
      {
        if (this.isAnonymous)
          throw CriticError("not supported; user is anonymous");

        if (!(repository instanceof CriticRepository))
          throw CriticError("invalid argument: expected Repository object");

        path = String(path);
        filter_type = String(filter_type);

        if (filter_type != "reviewer" && filter_type != "watcher" && filter_type != "ignored")
          throw CriticError("invalid argument: filter type must be 'reviewer', 'watcher' or 'ignored'");
        if (/[^\/]\*\*|\*\*[^\/]/.test(path))
          throw CriticError("invalid wildcards in path argument");

        if (delegates)
        {
          delegates = String(delegates).split(/\s*,\s*|\s+/g);
          for (var index = 0; index < delegates.length; ++index)
          {
            if (db.execute("SELECT 1 FROM users WHERE name=%s", delegates[index]).length == 0)
              throw CriticError(format("invalid delegate '%s': no such user", delegates[index]));
          }
          delegates = delegates.join(",");
        }
        if (!delegates)
          delegates = null;

        if (filter_type != "reviewers" && delegates)
          throw CriticError(format("'%s' filter should not have delegates", filter_type));

        var filter_id = db.execute("INSERT INTO filters (repository, uid, path, type, delegate) " +
                                   "     VALUES (%d, %d, %s, %s, %s) " +
                                   "  RETURNING id",
                                   repository.id, this.id, path, filter_type, delegates);
        db.commit();

        return new CriticFilter(this, repository, { id: filter_id,
                                                    path: path,
                                                    type: filter_type,
                                                    delegates: delegates });
      }
  }
});

function CriticAnonymousUser()
{
  this.id = null;
  this.name = null;
  this.email = null;
  this.fullname = null;
  this.isAnonymous = true;

  Object.freeze(this);
}

CriticAnonymousUser.prototype = Object.create(CriticUser.prototype);

Object.defineProperty(CriticUser, "current", { get: function () { return global.user; }, enumerable: true });
