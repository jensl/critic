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

function CriticLog(user)
{
  this.write = function ()
    {
      var text, options, category = "default";

      if (typeof arguments[arguments.length - 1] == "object")
      {
        options = arguments[arguments.length - 1];
        text = format.apply(null, Array.prototype.slice.call(arguments, 0, arguments.length - 1));
      }
      else
        text = format.apply(null, arguments);

      if (options)
        category = "" + options.category;

      db.execute("INSERT INTO extensionlog (extension, uid, category, text) VALUES (%d, %d, %s, %s)",
                 extension_id, user.id, category, text);
      db.commit();
    };

  function getQuery(data)
  {
    var terms = ["extensionlog.extension = %d", "extensionlog.uid = %d"];
    var parameters = [extension_id, global.user.id];

    if (data && typeof data == "object")
    {
      if (data.timeStart)
      {
        if (typeof data.timeStart == "object")
        {
          terms.push("extensionlog.time >= %s::timestamp");
          parameters.push(Date.prototype.toSQLTimestamp.call(data.timeStart));
        }
        else
        {
          terms.push("extensionlog.time >= now() - %s::interval");
          parameters.push(String(data.timeStart));
        }
      }

      if (data.timeEnd)
      {
        if (typeof data.timeEnd == "object")
        {
          terms.push("extensionlog.time <= %s::timestamp");
          parameters.push(Date.prototype.toSQLTimestamp.call(data.timeEnd));
        }
        else
        {
          terms.push("extensionlog.time <= now() - %s::interval");
          parameters.push(String(data.timeEnd));
        }
      }

      if (data.category)
      {
        terms.push("extensionlog.category = %s");
        parameters.push(String(data.category));
      }
    }

    return { where: terms.join(" AND "), parameters: parameters };
  }

  this.fetch = function (data)
    {
      var query = getQuery(data);
      var result = db.execute.apply(db, ["SELECT uid, category, time, text FROM extensionlog WHERE " + query.where + " ORDER BY time ASC"].concat(query.parameters));
      var users = {};
      var log = [];

      for (var index = 0; index < result.length; ++index)
      {
        var row = result[index];
        var user = users[row.uid];

        if (!user)
          user = users[row.uid] = new CriticUser({ id: row.uid });

        log.push(Object.freeze({ user: user, time: row.time, category: row.category, text: row.text }));
      }

      return log;
    };

  this.remove = function (data)
    {
      var query = getQuery(data);

      db.execute.apply(db, ["DELETE FROM extensionlog WHERE " + query.where].concat(query.parameters));
      db.commit();
    };
}
