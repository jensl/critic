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

function addReviewFiltersDialog(options)
{
  var title, message;

  if (options.filter_type == "reviewer")
  {
    title = "Add Reviewer";
    message = "<p>Make specified users reviewers of given path during this review.</p>";
  }
  else
  {
    title = "Add Watcher";
    message = "<p>Make specified users watchers of given path during this review.  "
            +    "If a user would normally be a reviewer of the path, he/she is "
            +    "reduced to just a watcher.</p>";
  }

  var content = $("<div class='comment' title='" + title + "'>"
                +   message
                +   "<p>"
                +     "<b>User name(s):</b><br>"
                +     "<input class='name sourcefont' style='width: 100%'><br>"
                +     "<b>Directory:</b><br>"
                +     "<input class='path sourcefont' style='width: 100%'"
                +           " placeholder='Leave empty for \"everything\"'>"
                +   "</p>"
                + "</div>");

  function finish()
  {
    var names = content.find("input.name").val().trim().split(/[, ]+/);
    var path = content.find("input.path").val().trim();

    /* Filter out empty names. */
    names = names.filter(function (name) { return name; });

    if (!path)
      path = "/";

    if (names.length)
      return options.callback(names, path);
    else
      return false;
  }

  function checkFinished()
  {
    if (finish())
    {
      $(content).dialog("close");

      if (options.reload_page)
        location.reload();
    }
  }

  function handleKeypress(ev)
  {
    if (ev.keyCode == 13)
      checkFinished();
  }

  content.find("input").keypress(handleKeypress);

  var buttons = {
    "Add Filter": function () { checkFinished(); },
    "Cancel": function () { content.dialog("close"); }
  };

  content.dialog({ width: 600, height: "auto",
                   modal: true,
                   buttons: buttons });

  function enableAutoCompletion(result)
  {
    content.find("input.name").autocomplete({
      source: AutoCompleteUsers(result.users)
    });
    content.find("input.path").autocomplete({
      source: AutoCompletePath(result.paths),
      html: true
    });
  }

  var data = { values: [ "users", "paths" ] };

  if (window.review)
    /* Called from review front-page. */
    data.review_id = review.id;
  else
    /* Called from "Create Review" page. */
    data.changeset_ids = review_data.changeset_ids;

  var operation = new Operation({ action: "get auto-complete data",
                                  url: "getautocompletedata",
                                  data: data,
                                  callback: enableAutoCompletion });

  operation.execute();
}
