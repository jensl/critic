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

function shortDate(date)
{
  function pad(number, width)
  {
    var result = String(number);
    while (result.length < width)
      result = "0" + result;
    return result;
  }

  return (pad(date.getFullYear(), 4) +
          "-" + pad(date.getMonth() + 1, 2) +
          "-" + pad(date.getDate(), 2) +
          " " + pad(date.getHours(), 2) +
          ":" + pad(date.getMinutes(), 2));
}

function triggerUpdate(branch_id)
{
  var operation = new Operation({ action: "trigger update",
                                  url: "triggertrackedbranchupdate",
                                  data: { branch_id: branch_id }});

  if (operation.execute())
  {
    done = $("<div title='Status' style='text-align: center; padding-top: 2em'>Branch update triggered.</div>");
    done.dialog({ modal: true, buttons: { OK: function () { done.dialog("close"); }}});
  }
}

function enableTracking(branch_id, remote, current_remote_name)
{
  function finish()
  {
    var operation = new Operation({ action: "enable tracking",
                                    url: "enabletrackedbranch",
                                    data: { branch_id: branch_id,
                                            new_remote_name: remote_name.val() }});

    return Boolean(operation.execute());
  }

  var self = this;
  var content = $("<div class='enabletracking' title='Enable Tracking'><p><b>Remote branch name:</b><br><input></p></div>");
  var remote_name = content.find("input");

  remote_name
    .val(current_remote_name)
    .autocomplete({ source: AutoCompleteRef(remote, "refs/heads/"), html: true });

  var buttons = {
    "Enable Tracking": function () { if (finish()) { content.dialog("close"); location.reload(); } },
    "Cancel": function () { content.dialog("close"); }
  };

  content.dialog({ width: 400,
                   buttons: buttons });
}

function disableTracking(branch_id)
{
  var operation = new Operation({ action: "disable tracking",
                                  url: "disabletrackedbranch",
                                  data: { branch_id: branch_id }});

  if (operation.execute())
    location.reload();
}

function watchReview()
{
  $.ajax({ async: false,
           url: "watchreview?review=" + review.id + "&user=" + user.name,
           dataType: "text",
           success: function (data)
             {
               if (data == "ok")
                 location.reload();
               else
                 reportError("watch review", "Server reply: <i style='white-space: pre'>" + htmlify(data) + "</i>");
             },
           error: function ()
             {
               reportError("watch review", "Request failed.");
             }
         });
}

function unwatchReview()
{
  $.ajax({ async: false,
           url: "unwatchreview?review=" + review.id + "&user=" + user.name,
           dataType: "text",
           success: function (data)
             {
               if (data == "ok")
                 location.reload();
               else if (data == "error:isreviewer")
                 reportError("stop watching review", "The user is a reviewer!");
               else
                 reportError("stop watching review", "Server reply: <i style='white-space: pre'>" + htmlify(data) + "</i>");
             },
           error: function ()
             {
               reportError("stop watching review", "Request failed.");
             }
         });
}

function filterPartialChanges()
{
  var content = $("<div title='Filter Partial Changes'>Please select the commits to filter.</div>");

  function cancel()
  {
    content.dialog("close");
    overrideShowSquashedDiff = null;
  }

  content.dialog({ width: 800,
                   position: "top",
                   buttons: { Cancel: cancel },
                   resizable: false });

  overrideShowSquashedDiff = function (from_sha1, to_sha1)
    {
      overrideShowSquashedDiff = null;
      content.dialog("close");

      location.href = "filterchanges?review=" + review.id + "&first=" + from_sha1 + "&last=" + to_sha1;
    };
}

function updateFilters(filter_type)
{
  var content;

  if (filter_type == "reviewer")
    content = $("<div class='comment' title='Add Reviewer'><p>Make specified users reviewers of given path during this review.</p><p><b>User name(s):</b><br><input class='name sourcefont' style='width:100%'><br><b>Directory:</b><input class='path sourcefont' style='width:100%'></p></div>");
  else
    content = $("<div class='comment' title='Add Watcher'><p>Make specified users watchers of given path during this review.  If a user would normally be a reviewer of the path, he/she is reduced to just a watcher.</p><p><b>User name(s):</b><br><input class='name sourcefont' style='width: 100%'><br><b>Directory:</b><br><input class='path sourcefont' style='width:100%'></p></div>");

  function finish(type, force)
  {
    var name = content.find("input.name").val();
    var path = content.find("input.path").val();

    var names = name.split(/[, ]+/);

    if (!force)
    {
      if (/[?*]/.test(path))
      {
        var error = $("<div class='error' title='Invalid Path'><p>The entered path is not valid.  No wild-cards are allowed; the path must be a single directory or file.</p><p>If you believe your path actually adheres to these rules, and this error is incorrect, you can use the <b>Override</b> button below to override the error.</p></div>");

        error.dialog({ width: 400,
                       buttons: { "Try Again": function () { error.dialog("close"); content.find("input.path").focus(); },
                                  "Override": function () { error.dialog("close"); finish(type, true); } },
                       modal: true });

        return false;
      }
    }

    var operation = new Operation({ action: "update review filters",
                                    url: "addreviewfilters",
                                    data: { review_id: review.id,
                                            filters: [{ type: filter_type,
                                                        user_names: name.split(/[, ]+/),
                                                        paths: [path] }] }});

    return operation.execute() != null;
  }

  function checkFinished()
  {
    if (finish())
    {
      $(content).dialog("close");
      location.reload();
    }
  }

  function handleKeypress(ev)
  {
    if (ev.keyCode == 13)
      checkFinished();
  }

  var buttons = { Add: function () { checkFinished(); },
                  Cancel: function () { $(content).dialog("close"); } };

  content.dialog({ width: 600, height: "auto",
                   modal: true,
                   buttons: buttons });

  content.find("input.name").keypress(handleKeypress);
  content.find("input.path").keypress(handleKeypress);

  function enableAutoCompletion(result)
  {
    content.find("input.name").autocomplete({ source: AutoCompleteUsers(result.users) });
    content.find("input.path").autocomplete({ source: AutoCompletePath(result.paths), html: true });
  }

  var operation = new Operation({ action: "get auto-complete data",
                                  url: "getautocompletedata",
                                  data: { values: ["users", "paths"],
                                          review_id: review.id },
                                  callback: enableAutoCompletion })

  operation.execute();
}

function addReviewer()
{
  updateFilters("reviewer");
}

function addWatcher()
{
  updateFilters("watcher");
}

function removeReviewFilter(filter_id, filter_user, filter_type, filter_path, confirm)
{
  function finish()
  {
    var operation = new Operation({ action: "remove review filter",
                                    url: "removereviewfilter",
                                    data: { filter_id: filter_id }});

    if (operation.execute())
    {
      location.reload();
      return true;
    }
    else
      return false;
  }

  if (confirm)
  {
    var content = $("<div class='removefilter' title='Confirm'><p>Please confirm that you mean to remove the filter that makes</p><div class=user>" + htmlify(filter_user) + "</div><p>a " + filter_type + " of</p><div class=path>" + filter_path + "</div><p>An email will be sent the user about the change and its effect on assignments.</p></div>");

    content.dialog({ width: 400,
                     buttons: { "Remove the filter": function () { if (finish()) content.dialog("close"); },
                                "Do nothing": function () { content.dialog("close"); } },
                     modal: true });
  }
  else
    finish();
}

function applyParentFilters()
{
  var new_reviewers, new_watchers;

  $.ajax({ async: false,
           url: "queryparentfilters?review=" + review.id,
           dataType: "text",
           success: function (data)
             {
               if (/^ok$/m.test(data))
               {
                 var lines = data.split("\n");

                 new_reviewers = eval(lines[1]);
                 new_watchers = eval(lines[2]);
               }
               else
                 reportError("update review filters", "Server reply: <i style='white-space: pre'>" + htmlify(data) + "</i>");
             },
           error: function ()
             {
               reportError("update review filters", "Request failed.");
             }
         });

  if (new_reviewers instanceof Array && new_watchers instanceof Array)
  {
    var content = "<div title='Apply Upstream Filters'><p>By applying upstream filters to this review, the following new reviewers and watchers would be added:</p>";

    if (new_reviewers.length)
    {
      content += "<p>New reviewers:</p><ul>";
      new_reviewers.forEach(function (user) { content += "<li>" + htmlify(user.displayName + " <" + user.email + ">") + "</li>"; });
      content += "</ul>";
    }

    if (new_watchers.length)
    {
      content += "<p>New watchers:</p><ul>";
      new_watchers.forEach(function (user) { content += "<li>" + htmlify(user.displayName + " <" + user.email + ">") + "</li>"; });
      content += "</ul>";
    }

    content = $(content);

    function proceed()
    {
      var success = false;

      $.ajax({ async: false,
               url: "applyparentfilters?review=" + review.id,
               dataType: "text",
               success: function (data)
                 {
                   if (data == "ok")
                     success = true;
                   else
                     reportError("apply upstream filters", "Server reply: <i style='white-space: pre'>" + htmlify(data) + "</i>");
                 },
               error: function ()
                 {
                   reportError("apply upstream filters", "Request failed.");
                 }
             });

      return success;
    }

    content.dialog({ width: 400, modal: true, buttons: { "Apply Upstream Filters": function () { if (proceed()) { content.dialog("close"); location.reload(); } }, "Do Nothing": function () { content.dialog("close"); }}});
  }
}

function toggleReviewFilters(type, button)
{
  var table = $("table.reviewfilters." + type);
  var tbody = table.find("tbody");
  var tfoot = table.find("tfoot");

  if (tbody.hasClass("hidden"))
  {
    tbody.removeClass("hidden");
    tfoot.addClass("hidden");
    button.button("option", "label", "Hide Custom Filters");
  }
  else
  {
    tbody.addClass("hidden");
    tfoot.removeClass("hidden");
    button.button("option", "label", "Show Custom Filters");
  }
}

function prepareRebase()
{
  var rebase_type_dialog;

  function finish()
  {
    var inplace = rebase_type_dialog.find("input#inplace:checked").size() != 0;

    if (inplace)
    {
      var operation = new Operation({ action: "prepare rebase",
                                      url: "preparerebase",
                                      data: { review_id: review.id }});

      if (operation.execute())
      {
        rebase_type_dialog.dialog("close");

        var finished =
          $("<div title='Rebase Prepared!'>"
          +   "<p>"
          +     "You may now push the rebased branch, using \"git push -f\".  "
          +     "Any attempt to push changes to this review by other users will "
          +     "be rejected until you've completed the rebase, or aborted it."
          +   "</p>"
          +   "<p>"
          +     "<b>Note:</b> Remember that one commit on the rebased branch must "
          +     "reference a tree that is identical to the one referenced by the "
          +     "current head of the review branch.  If this is not the case, your "
          +     "push will be rejected."
          +   "</p>"
          + "</div>");

        finished.dialog({ width: 400,
                          modal: true,
                          buttons: { Close: function () { finished.dialog("close"); location.reload(); }}
                        });
      }
    }
    else
    {
      rebase_type_dialog.dialog("close");

      var select_upstream_dialog =
        $("<div class='specifyupstream' title='Specify New Upstream Commit'>"
        +   "<p>"
        +     "Unless you squashed the whole branch into a single commit, please specify "
        +     "the new upstream commit onto which the review branch is rebased, either by "
        +     "entering a SHA-1 sum or by selecting one of the suggested tags:"
        +   "</p>"
        +   "<p>"
        +     "<label><input name='single' type='checkbox'>Branch squashed into a single commit.</label>"
        +   "</p>"
        +   "<p>"
        +     "<b>SHA-1:</b><input name='sha1' size=40>"
        +   "</p>"
        +   "<p>"
        +     "<b>Tag:</b>"
        +     "<select disabled>"
        +       "<option value='none'>Fetching suggestions...</option>"
        +     "</select>"
        +   "</p>"
        + "</div>");

      var select_upstream_dialog_closed = false;

      function populateSuggestedUpstreams(result)
      {
        if (result)
        {
          var upstreams = result.upstreams.map(
            function (tag)
            {
              return "<option value='" + htmlify(tag) + "'>" + htmlify(tag) + "</option>";
            });

          var select = select_upstream_dialog.find("select").get(0);

          if (upstreams.length != 0)
          {
            select.innerHTML = "<option value='none'>Found " + upstreams.length + " likely upstreams:</option>" + upstreams.join("");
            select.disabled = single.checked;
          }
          else
            select.innerHTML = "<option value='none'>(No likely upstreams found.)</option>";
        }
      }

      var fetch_upstreams = new Operation({ action: "fetch suggested upstream commits",
                                            url: "suggestupstreams",
                                            data: { review_id: review.id },
                                            callback: populateSuggestedUpstreams });

      fetch_upstreams.execute();

      var single = select_upstream_dialog.find("input").get(0);
      var sha1 = select_upstream_dialog.find("input").get(1);
      var tag = select_upstream_dialog.find("select").get(0);

      single.onclick = function ()
        {
          sha1.disabled = single.checked;
          tag.disabled = single.checked || tag.options.length == 1;
        };

      function finishMove()
      {
        var upstream;

        if (single.checked)
          upstream = "0000000000000000000000000000000000000000";
        else if (tag.value != "none" && sha1.value != "")
          alert("Ambiguous input! Please leave either SHA-1 or tag empty.");
        else if (tag.value == "none" && !/^[0-9a-f]{40}$/i.test(sha1.value))
          alert("Invalid input! Please specify a full 40-character SHA-1 sum.");
        else if (sha1.value != "")
          upstream = sha1.value;
        else
          upstream = tag.value;

        if (typeof upstream == "string")
        {
          var operation = new Operation({ action: "prepare rebase",
                                          url: "preparerebase",
                                          data: { review_id: review.id,
                                                  new_upstream: upstream }});

          if (operation.execute())
          {
            select_upstream_dialog.dialog("close");

            var finished =
              $("<div title='Rebase Prepared!'>"
              +   "<p>"
              +     "You may now push the rebased branch, using \"git push -f\".  "
              +     "Any attempt to push changes to this review by other users will "
              +     "be rejected until you've completed the rebase, or aborted it."
              +   "</p>"
              +   "<p>"
              +     "<b>Important:</b> Remember not to push any new changes to the "
              +     "review with this push; such changes will be very difficult to "
              +     "see or review."
              +   "</p>"
              + "</div>");

            finished.dialog({ width: 400,
                              modal: true,
                              buttons: { Close: function () { finished.dialog("close"); location.reload(); }}
                            });
          }
        }
      }

      select_upstream_dialog.dialog({ width: 400,
                                      modal: true,
                                      buttons: { Continue: function () { finishMove(); },
                                                 Cancel: function () { select_upstream_dialog.dialog("close"); }},
                                      close: function () { select_upstream_dialog_closed = true; }
                                    });
    }

    return true;
  }

  function start(supports_move)
  {
    rebase_type_dialog =
      $("<div title='Prepare Rebase'>"
      +   "<p>Please select rebase type:</p>"
      +   "<dl>"
      +     "<dt><label><input id='inplace' type='radio' name='rebasetype' checked>History Rewrite / In-place</label></dt>"
      +     "<dd>Rebase on-top of the same upstream commit that only changes the history on the branch.</dd>"
      +     "<dt><label><input id='move' type='radio' name='rebasetype'" + (supports_move ? "" : " disabled") + ">New Upstream / Move</label></dt>"
      +     "<dd>" + (supports_move ? "" : "<div class='notsupported'>[Not supported for this review!]</div>") + "Rebase on-top of a different upstream commit.  Can also change the history on the branch in the process.</dd>"
      +   "</dl>"
      + "</div>");

    rebase_type_dialog.dialog({ width: 400,
                                modal: true,
                                buttons: { Continue: function () { finish(); },
                                           Cancel: function () { rebase_type_dialog.dialog("close"); }}
                              });
  }

  var operation = new Operation({ action: "check rebase possibility",
                                  url: "checkrebase",
                                  data: { review_id: review.id }});

  var result = operation.execute();

  if (result)
    start(result.available == "both");
}

function cancelRebase()
{
  var operation = new Operation({ action: "cancel rebase",
                                  url: "cancelrebase",
                                  data: { review_id: review.id }});

  if (operation.execute())
    location.reload();
}

function revertRebase(rebase_id)
{
  var confirm_dialog = $("<div title=Please Confirm'><p>Are you sure you want to revert the rebase?</p></div>");

  function finish()
  {
    var operation = new Operation({ action: "revert rebase",
                                    url: "revertrebase",
                                    data: { review_id: review.id,
                                            rebase_id: rebase_id }});

    if (operation.execute())
    {
      confirm_dialog.dialog("close");
      location.reload();
    }
  }

  confirm_dialog.dialog({ width: 400,
                          modal: true,
                          buttons: { "Revert Rebase": function () { finish(); },
                                     "Do Nothing": function () { confirm_dialog.dialog("close"); }}
                        });
}

function excludeRecipient(user_id)
{
  var operation = new Operation({ action: "exclude recipient",
                                  url: "addrecipientfilter",
                                  data: { review_id: review.id,
                                          user_id: user_id,
                                          include: false }});

  if (operation.execute())
    location.reload();
}

function includeRecipient(user_id)
{
  var operation = new Operation({ action: "include recipient",
                                  url: "addrecipientfilter",
                                  data: { review_id: review.id,
                                          user_id: user_id,
                                          include: true }});

  if (operation.execute())
    location.reload();
}

$(document).ready(function ()
  {
    $("tr.commit td.summary").each(function (index, element)
      {
        var users = $(element).attr("critic-reviewers");
        if (users)
        {
          users = users.split(",");

          $(element).find("a.commit").tooltip({
            fade: 250,
            bodyHandler: function ()
              {
                var html = "<div class='summary-tooltip'><div class='header'>Needs review from</div>";

                for (var index = 0; index < users.length; ++index)
                {
                  var match = /([^:]+):(current|absent|retired)/.exec(users[index]);
                  var fullname = match[1];
                  var status = match[2];
                  if (status != "retired")
                  {
                    html += "<div class='reviewer'>" + htmlify(fullname);
                    if (status == "absent")
                      html += "<span class='absent'> (absent)</span>";
                    html += "</div>";
                  }
                }

                return $(html + "</div>");
              },
            showURL: false
          });
        }
      });

    $("td.straggler.no-email").each(function (index, element)
      {
        $(element).tooltip({
          fade: 250,
          bodyHandler: function ()
            {
              return $("<div class='no-email-tooltip'><strong>This user has not enabled the <u>email.activated</u> preference!</strong></div>");
            }
        });
      });

    $("a[title]").tooltip({ fade: 250 });

    var reviewfilters = [];

    $("table.shared button.accept").click(function (ev)
      {
        var target = $(ev.currentTarget);
        var paths = JSON.parse(target.attr("critic-paths"));
        var user_ids = JSON.parse(target.attr("critic-user-ids"));

        reviewfilters.push({ type: "watcher",
                             user_ids: user_ids,
                             paths: paths });

        $("table.shared td.buttons > span").css("display", "inline");

        target.parents("td.buttons").children("button").css("visibility", "hidden");
        target.parents("tr.reviewers").children("td.willreview").css("text-decoration", "line-through");
      });

    $("table.shared button.deny").click(function (ev)
      {
        var target = $(ev.currentTarget);
        var paths = JSON.parse(target.attr("critic-paths"));

        reviewfilters.push({ type: "watcher",
                             user_ids: [user.id],
                             paths: paths });

        $("table.shared td.buttons > span").css("display", "inline");

        target.parents("td.buttons").children("button").css("visibility", "hidden");
        target.parents("tr.reviewers").find("td.willreview span.also").css("text-decoration", "line-through");
      });

    $("table.shared button.cancel").click(function (ev)
      {
        location.reload();
      });

    $("table.shared button.confirm").click(function (ev)
      {
        var operation = new Operation({ action: "add review filters",
                                        url: "addreviewfilters",
                                        data: { review_id: review.id,
                                                filters: reviewfilters }});

        if (operation.execute())
        {
          $("table.shared td.buttons > span").css("display", "none");
          reviewfilters = [];
          location.reload();
        }
      });

    $("button.preparerebase").click(prepareRebase);
    $("button.cancelrebase").click(cancelRebase);
  });
