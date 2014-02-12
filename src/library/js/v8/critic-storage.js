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

function CriticStorage(user)
{
  this.get = function (key)
    {
      if (key.length > 64)
        throw CriticError(format("%s: key length exceeds 64 characters", key));

      var result = db.execute("SELECT text FROM extensionstorage WHERE extension=%d AND uid=%d AND key=%s", extension_id, user.id, key)[0];
      if (result)
        return result.text;
      else
        return null;
    };

  this.set = function (key, text)
    {
      if (key.length > 64)
        throw CriticError(format("%s: key length exceeds 64 characters", key));

      /* Roll the current transaction back first just to make sure we don't
         commit anything else by mistake.  The current transaction (if there is
         one) should be "empty," and if it isn't, we don't want to keep it. */
      db.rollback();

      var result = db.execute("SELECT 1 FROM extensionstorage WHERE extension=%d AND uid=%d AND key=%s", extension_id, user.id, key)[0];
      if (result)
        db.execute("UPDATE extensionstorage SET text=%s WHERE extension=%d AND uid=%d AND key=%s", text, extension_id, user.id, key);
      else
        db.execute("INSERT INTO extensionstorage (extension, uid, key, text) VALUES (%d, %d, %s, %s)", extension_id, user.id, key, text);

      /* This code has a possible race-condition: someone else might insert a
         row for this extension-user-key triple between the SELECT and the
         INSERT above.  It would be excessively unlikely, though, and it would
         simply cause the transaction commit to fail with a constraint violation
         error (the extension-user-key triple is the table's primary key.) */
      db.commit();
    };

  this.remove = function (key)
    {
      /* Roll the current transaction back first just to make sure we don't
         commit anything else by mistake.  The current transaction (if there is
         one) should be "empty," and if it isn't, we don't want to keep it. */
      db.rollback();
      db.execute("DELETE FROM extensionstorage WHERE extension=%d AND uid=%d AND key=%s", extension_id, user.id, key);
      db.commit();
    };
}
