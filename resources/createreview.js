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

/* -*- Mode: js; js-indent-level: 2; indent-tabs-mode: nil -*- */

var reviewfilters = [];
var recipients_mode = "opt-out", recipients_included = {}, recipients_excluded = {};

function submitReview()
{
  var branch_name = document.getElementById("branch_name");
  var summary = document.getElementById("summary");
  var description = document.getElementById("description").value.trim();

  if (invalid_branch_name && branch_name.value == invalid_branch_name)
  {
    alert("You need to edit the branch name, lazy!");
    branch_name.focus();
    return;
  }

  if (branch_name.value.length <= 4)
  {
    alert("A branch name that short is not a good review identifier.  Please elaborate a little bit.");
    branch_name.focus();
    return;
  }

  if (summary.value.length <= 8)
  {
    alert("A summary that short is not very meaningful.  Please elaborate a little bit.");
    summary.focus();
    return;
  }

  var data = { repository_id: repository.id,
               commit_ids: review.commit_ids,
               branch: "r/" + branch_name.value,
               summary: summary.value.trim(),
               reviewfilters: reviewfilters,
               recipientfilters: { mode: recipients_mode,
                                   included: Object.keys(recipients_included),
                                   excluded: Object.keys(recipients_excluded) },
               applyfilters: $("input.applyfilters:checked").size() != 0,
               applyparentfilters: $("input.applyparentfilters:checked").size() != 0 };

  if (description)
    data.description = description;
  if (typeof fromBranch == "string")
    data.frombranch = fromBranch;
  if (typeof trackedbranch == "object")
    data.trackedbranch = trackedbranch;

  var operation = new Operation({ action: "create review",
                                  url: "submitreview",
                                  data: data });
  var result = operation.execute();

  if (result)
  {
    if (result.extensions_output)
      showMessage("Review Created",
                  "Extension Output",
                  "<pre>" + htmlify(result.extensions_output) + "</pre>",
                  function () { location.href = "r/" + result.review_id; });
    else
      location.href = "r/" + result.review_id;
  }
}

function updateReviewersAndWatchers(new_reviewfilters)
{
  var success = false;

  if (!new_reviewfilters)
    new_reviewfilters = reviewfilters;

  var data = { repository_id: repository.id,
               commit_ids: review.commit_ids,
               reviewfilters: new_reviewfilters,
               applyfilters: $("input.applyfilters:checked").size() != 0,
               applyparentfilters: $("input.applyparentfilters:checked").size() != 0 };

  var operation = new Operation({ action: "update filters",
                                  url: "reviewersandwatchers",
                                  data: data });
  var result = operation.execute();

  if (result)
  {
    $("table.filters").replaceWith(result.html);
    $("table.filters").find("button").button();

    connectApplyFilters();

    reviewfilters = new_reviewfilters;
    return true;
  }
  else
    return false;
}

function updateFilters(add_reviewer)
{
  var content;
  if (add_reviewer)
    content = $("<div class='comment' title='Add Reviewer'><p>Make specified users reviewers of given path during this review.</p><p><b>User name(s):</b><br><input class='name' style='width: 100%'><br><b>Directory:</b><input class='path' style='width: 100%'></p></div>");
  else
    content = $("<div class='comment' title='Add Watcher'><p>Make specified users watchers of given path during this review.  If a user would normally be a reviewer of the path, he/she is reduced to just a watcher.</p><p><b>User name(s):</b><br><input class='name' style='width: 100%'><br><b>Directory:</b><br><input class='path' style='width: 100%'></p></div>");

  function finish(type)
  {
    var name = content.find("input.name").val();
    var path = content.find("input.path").val();

    var names = {};

    name.split(/[, ]+/).forEach(function (name) { names[name] = true; });

    new_reviewfilters = [];

    for (var index = 0; index < reviewfilters.length; ++index)
      if (!(reviewfilters[index].username in names) || reviewfilters[index].path != path)
        new_reviewfilters.push(reviewfilters[index]);

    for (var name in names)
      new_reviewfilters.push({ username: name,
                               type: add_reviewer ? "reviewer" : "watcher",
                               path: path });

    return updateReviewersAndWatchers(new_reviewfilters);
  }

  var buttons = { Add: function () { if (finish()) { $(content).dialog("close"); } },
                  Cancel: function () { $(content).dialog("close"); } };

  content.dialog({ width: 600, height: 250,
                   buttons: buttons });
}

function addReviewer()
{
  updateFilters(true);
}

function addWatcher()
{
  updateFilters(false);
}

function editRecipientList()
{
  var recipient_list_dialog =
    $("<div id='recipients' title='Edit Recipient List'>"
    +   "<p>The recipient list determines the list of users that receive "
    +      "e-mails about various updates to the review.  The recipient "
    +      "list is constructed from the list of users associated with the "
    +      "review (reviewers and watchers) either in an opt-in or opt-out "
    +      "fashion.  The default is opt-out, meaning all associated users "
    +      "receive e-mails unless they specifically ask not to.  By "
    +      "choosing opt-in mode, the review owner can restrict the list "
    +      "of recipients.</p>"
    +   "<p>Note: the review owner (you) is always included in the "
    +      "recipient list.</p>"
    +   "<table>"
    +     "<tr><td class=key>Mode:</td><td class=value>"
    +       "<select id='mode'>"
    +         "<option value='opt-out'>Opt-out (all users not specified below receive e-mails)</option>"
    +         "<option value='opt-in'>Opt-in (only users specified below receive e-mails)</option>"
    +       "</select>"
    +     "</td></tr>"
    +     "<tr><td class=key>Users:</td><td class=value>"
    +       "<input id='users'>"
    +     "</td></tr>"
    +   "</table>"
    + "</div>");

  if (recipients_mode == "opt-out")
    names = Object.keys(recipients_excluded);
  else
    names = Object.keys(recipients_included);

  recipient_list_dialog.find("#mode").val(recipients_mode);
  recipient_list_dialog.find("#users").val(names.join(", "));

  function save()
  {
    recipients_mode = recipient_list_dialog.find("#mode").val();
    recipients_included = {};
    recipients_excluded = {};

    var users = recipient_list_dialog.find("#users").val().split(/[\s,]+/g);
    for (var index = 0; index < users.length; ++index)
    {
      var name = users[index];
      if (name)
        if (recipients_mode == "opt-in")
          recipients_included[name] = true;
        else
          recipients_excluded[name] = true;
    }

    var mode;

    if (recipients_mode == "opt-in")
      if (Object.keys(recipients_included).length != 0)
      {
        mode = "No-one except ";
        users = recipients_included;
      }
      else
        mode = "No-one at all";
    else
      if (Object.keys(recipients_excluded).length != 0)
      {
        mode = "Everyone except ";
        users = recipients_excluded;
      }
      else
        mode = "Everyone";

    $("span.mode").text(mode);

    if (users)
    {
      var names = [];

      for (var name in users)
        names.push(users[name]);

      $("span.users").text(names.join(", "));
    }

    recipient_list_dialog.dialog("close");
  }

  function cancel()
  {
    recipient_list_dialog.dialog("close");
  }

  recipient_list_dialog.dialog({ width: 600,
                                 modal: true,
                                 buttons: { Save: save, Cancel: cancel }});

  recipient_list_dialog.find("#users").autocomplete({ source: AutoCompleteUsers(users) });
}

function connectApplyFilters()
{
  $("tr.applyfilters").click(function (ev)
    {
      if (ev.target.nodeName.toLowerCase() != "input")
      {
        var checkbox = $(ev.currentTarget).find("input");
        checkbox.get(0).checked = !checkbox.get(0).checked;
        updateReviewersAndWatchers();
      }
    });

  $("tr.applyfilters input").click(function (ev)
    {
      updateReviewersAndWatchers();
    });
}

$(document).ready(function ()
  {
    connectApplyFilters();

    $("select.repository").change(
      function ()
      {
        var name = $(this).val();

        if (default_remotes[name])
        {
          $("select.remotehost").val(default_remotes[name][0]);
          $("input.remotepath").val(default_remotes[name][1]);
        }

        if (default_branches[name])
          $("input.upstreamcommit").val(default_branches[name] ? "refs/heads/" + default_branches[name] : "");
      });

    function getCurrentRemote()
    {
      var host = $("select.remotehost").val();
      if (host.indexOf(":") == -1)
        host += ":";
      var path = $("input.remotepath").val();
      if (!/[:\/]$/.test(host) && !/^\//.test(path))
        return host + "/" + path;
      else
        return host + path;
    }

    var input_workbranch = $("input.workbranch");

    input_workbranch.autocomplete({ source: AutoCompleteRef(getCurrentRemote, "refs/heads/"), html: true });
    input_workbranch.keypress(
      function (ev)
      {
        if (ev.keyCode == 13)
          $("button.fetchbranch").click();
      });

    var input_upstreamcommit = $("input.upstreamcommit");

    input_upstreamcommit.autocomplete({ source: AutoCompleteRef(), html: true });

    $("button.fetchbranch").click(
      function ()
      {
        var branch = $("input.workbranch").val().trim();
        var upstream = $("input.upstreamcommit").val().trim();

        if (!branch)
        {
          showMessage("Invalid input!", "Invalid input!", "Please provide a non-empty branch name.");
          return;
        }

        if (!upstream)
        {
          showMessage("Invalid input!", "Invalid input!", "Please provide a non-empty upstream commit reference.");
          return;
        }

        function finish(result)
        {
          if (result)
            location.href = ("/createreview" +
                             "?repository=" + encodeURIComponent($("select.repository").val()) +
                             "&commits=" + encodeURIComponent(result.commit_ids) +
                             "&remote=" + encodeURIComponent(getCurrentRemote()) +
                             "&branch=" + encodeURIComponent($("input.workbranch").val()) +
                             "&upstream=" + encodeURIComponent($("input.upstreamcommit").val()) +
                             "&reviewbranchname=" + encodeURIComponent($("input.workbranch").val()));
        }

        var operation = new Operation({ action: "fetch remote branch",
                                        url: "fetchremotebranch",
                                        data: { repository_name: $("select.repository").val(),
                                                remote: getCurrentRemote(),
                                                branch: $("input.workbranch").val(),
                                                upstream: $("input.upstreamcommit").val() },
                                        wait: "Fetching branch...",
                                        callback: finish });

        operation.execute();
      });
  });
