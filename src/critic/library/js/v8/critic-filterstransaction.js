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

var filterstransaction_internals = {};
var filterstransaction_id_counter = 0;

function CriticFiltersTransaction(repository)
{
  var internal_id = filterstransaction_id_counter++;

  filterstransaction_internals[internal_id] =
    { transaction: this,
      added: {},
      removed: {} };

  Object.defineProperty(this, "__id__", { value: internal_id });

  this.repository = repository;
}

function CriticFiltersTransaction_getInternals(transaction)
{
  var internals = filterstransaction_internals[transaction.__id__];
  if (!internals || transaction != internals.transaction)
    throw CriticError("invalid use");
  return internals;
}

CriticFiltersTransaction.prototype.addFilter =
  function (filter)
  {
    var internals = CriticFiltersTransaction_getInternals(this);

    if (!filter || typeof filter != "object")
      throw CriticError("invalid 'data' argument; expected object");

    var user = filter.user || {};
    var what = filter.what || {};
    var type = filter.type || "";
    var delegates = filter.delegates || null;

    if (!(user instanceof CriticUser))
      throw CriticError("invalid 'data.user' argument; expected User object");
    if (!(what instanceof CriticDirectory || what instanceof CriticFile))
      throw CriticError("invalid 'data.what' argument; expected Directory or File object");

    type = String(type);

    if (type != "reviewer" && type != "watcher")
      throw CriticError("invalid 'type' argument; expected \"reviewer\" or \"watcher\"");
    if (delegates && !Array.prototype.every.call(delegates, function (item) { return item instanceof CriticUser; }))
      throw CriticError("invalid 'delegates' argument; expected array of User objects");

    var existing = this.repository.filters.users[user.name];
    var removed = internals.removed[user.id];

    function isNonConflicting(filter)
    {
      return what.path != filter.path || type != filter.type;
    }

    if (removed && !removed.every(isNonConflicting))
      throw CriticError("added filter is identical to existing filter removed in this transaction");

    if (existing && !existing.every(isNonConflicting))
      throw CriticError("added filter is identical to existing filter");

    var added = internals.added[user.id];

    if (!added)
      added = internals.added[user.id] = [];

    added.push({ path: what.path,
                 directory_id: what instanceof CriticDirectory ? what.id : 0,
                 file_id: what instanceof CriticFile ? what.id : 0,
                 type: type,
                 delegate: delegates.map(function (user) { return user.name; }).join(",") });
  };

CriticFiltersTransaction.prototype.removeFilter =
  function (filter)
  {
    var internals = CriticFiltersTransaction_getInternals(this);

    if (!filter || typeof filter != "object")
      throw CriticError("invalid 'data' argument; expected object");

    var user = filter.user || {};
    var what = filter.what || {};
    var type = filter.type || "";

    if (!(user instanceof CriticUser))
      throw CriticError("invalid 'user' argument; expected User object");
    if (!(what instanceof CriticDirectory || what instanceof CriticFile))
      throw CriticError("invalid 'what' argument; expected Directory or File object");

    type = String(type);

    if (type != "reviewer" && type != "watcher")
      throw CriticError("invalid 'type' argument; expected \"reviewer\" or \"watcher\"");

    function isNonConflicting(filter)
    {
      return what.path != filter.path || type != filter.type;
    }

    var added = internals.added[user.id];

    if (added && !added.every(isNonConflicting))
      throw CriticError("removed filter is identical to existing filter added in this transaction");

  };
