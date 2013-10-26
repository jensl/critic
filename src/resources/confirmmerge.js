/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2012 Jens Lindström, Opera Software ASA

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

overrideShowSquashedDiff = function (from_sha1)
{
  location.href = "/confirmmerge?id=" + confirmation_id + "&tail=" + from_sha1;
}

$(document).ready(function ()
  {
    $("button").button();

    $("button.confirmAll").click(function (ev)
      {
        var tail = "";
        if (typeof tail_sha1 == "string")
          tail = "&tail=" + tail_sha1;
        location.href = "/confirmmerge?id=" + confirmation_id + "&confirm=yes" + tail;
      });

    $("button.confirmNone").click(function (ev)
      {
        location.href = "/confirmmerge?id=" + confirmation_id + "&confirm=yes&tail=" + merge_sha1;
      });

    $("button.cancel").click(function (ev)
      {
        location.href = "/confirmmerge?id=" + confirmation_id + "&cancel=yes";
      });

    if (confirmed)
    {
      var content = $("<div title='Merge Confirmed'><p>Please repeat the 'git push' command that failed and redirected you here.  It will now allow this merge commit, and the additional commits it contributes listed on this page, to be added to the review.</p></div>");
      content.dialog({ width: 600, height: 225, modal: true, buttons: { OK: function () { content.dialog("close"); }}});
    }
  });
