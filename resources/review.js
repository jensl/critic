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

function updateDraftStatus(data)
{
  if (typeof data == "string")
  {
    var match = /^ok:(?:.*,)?approved=(\d+),disapproved=(\d+),(?:approvedBinary=(\d+),disapprovedBinary=(\d+),)?comments=(\d+),reopened=(\d+),closed=(\d+),morphed=(\d+)$/.exec(data);

    if (!match)
      return;

    data = { reviewedNormal: parseInt(match[1]),
             unreviewedNormal: parseInt(match[2]),
             reviewedBinary: parseInt(match[3]),
             unreviewedBinary: parseInt(match[4]),
             writtenComments: parseInt(match[5]),
             reopenedIssues: parseInt(match[6]),
             resolvedIssues: parseInt(match[7]),
             morphedChains: parseInt(match[8]) }
  }

  var items = [];

  function renderCount(count, what)
  {
    return count + " " + what + (count != 1 ? "s" : "");
  }

  if (data.reviewedNormal != '0')
    items.push("<span class='approved'>reviewed " + renderCount(data.reviewedNormal, "line") + "</span>");
  if (data.unreviewedNormal != '0')
    items.push("<span class='disapproved'>unreviewed " + renderCount(data.unreviewedNormal, "line") + "</span>");
  if (data.reviewedBinary != '0')
    items.push("<span class='approved'>reviewed " + renderCount(data.reviewedBinary, "binary file") + "</span>");
  if (data.unreviewedBinary != '0')
    items.push("<span class='disapproved'>unreviewed " + renderCount(data.unreviewedBinary, "binary file") + "</span>")
  if (data.writtenComments != '0')
    items.push("<span class='comments'>wrote " + renderCount(data.writtenComments, "comment") + "</span>");
  if (data.reopenedIssues != '0')
    items.push("<span class='reopened'>reopened " + renderCount(data.reopenedIssues, "issue") + "</span>");
  if (data.resolvedIssues != '0')
    items.push("<span class='closed'>resolved " + renderCount(data.resolvedIssues, "issue") + "</span>");
  if (data.morphedChains != '0')
    items.push("<span class='morphed'>morphed " + renderCount(data.morphedChains, "comment") + "</span>");

  var draftStatus = $("#draftStatus");

  if (items.length == 0)
    draftStatus.empty().nextAll("div.buttons").show();
  else
  {
    draftStatus.html("<span class='draft'>Draft:</span>"
                    + " " + items.join(", ") + " "
                    + "<span class='buttons'>"
                    +   "<button onclick='previewChanges();'>Preview</button>"
                    +   "<button onclick='submitChanges();'>Submit</button>"
                    +   "<button onclick='cancelChanges();'>Abort</button>"
                    + "</span>");
    draftStatus.find("button").button();
    draftStatus.nextAll("div.buttons").hide();
  }

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();
}

function markFile(status, file_id, parent_index)
{
  var id_prefix = parent_index !== null ? "p" + parent_index : "";
  var checkbox = document.getElementById(id_prefix + "a" + file_id);

  if (!checkbox)
    return;

  var changeset_ids;
  var reviewableFiles;

  if (parent_index !== null)
  {
    changeset_ids = [changeset[parent_index].id];
    reviewableFiles = changeset[parent_index].reviewableFiles;
  }
  else
  {
    changeset_ids = changeset.ids;
    reviewableFiles = changeset.reviewableFiles;
  }

  if (reviewableFiles[file_id] == status)
    return;

  var checked = status == "reviewed";

  if (checkbox.checked != checked)
    checkbox.checked = checked;

  var data = { review_id: review.id,
               reviewed: status == "reviewed",
               changeset_ids: changeset_ids,
               file_ids: [file_id] };

  function finish(result)
  {
    if (result)
    {
      reviewableFiles[file_id] = status;
      updateDraftStatus(result.draft_status);
    }
    else
      checkbox.checked = !checked;

    var all_checked;

    if (checkbox.checked)
    {
      all_checked = true;
      $(checkbox).parents("table.commit-files").find("td.approve.file > input").each(function (index, element) { if (!element.checked) all_checked = false; });
    }
    else
      all_checked = false;

    $(checkbox).parents("table.commit-files").find("td.approve.everything > input").each(function (index, element) { element.checked = all_checked; });
  }

  var callback;

  if (user.options.ui.asynchronousReviewMarking)
    callback = finish;
  else
    callback = null;

  var operation = new Operation({ action: "mark files as " + status,
                                  url: "markfiles",
                                  data: data,
                                  callback: callback });

  if (callback)
    operation.execute();
  else
    finish(operation.execute());
}

function markAllFiles(status)
{
  var changeset_ids = changeset.ids;
  var file_ids = [];

  var reviewableFiles = changeset.reviewableFiles;

  for (var file_id in reviewableFiles)
    if (/^\d+$/.test(file_id) && reviewableFiles[file_id] != status)
      file_ids.push(parseInt(file_id));

  if (!file_ids.length)
    return;

  var data = { review_id: review.id,
               reviewed: status == "reviewed",
               changeset_ids: changeset_ids,
               file_ids: file_ids };

  var operation = new Operation({ action: "mark files as " + status,
                                  url: "markfiles",
                                  data: data });
  var result = operation.execute();

  if (result)
  {
    for (var index = 0; index < file_ids.length; ++index)
      reviewableFiles[file_ids[index]] = status;
    updateDraftStatus(result.draft_status);
  }
  else
    checkbox.checked = status == "pending";
}

function previewChanges()
{
  location.href = "showbatch?review=" + review.id;
}

function submitChanges()
{
  function start()
  {
    function finish(remark)
    {
      var success = false;

      var data = { review_id: review.id };

      if (!/^\s*$/.test(remark))
        data.remark = remark;

      var operation = new Operation({ action: "submit changes",
                                      url: "submitchanges",
                                      data: data,
                                      wait: "Submitting changes..." });
      var result = operation.execute();

      if (result)
      {
        if (result.profiling)
          console.log(result.profiling);

        return true;
      }
      else
        return false;
    }

    function totalAdditionalHeight(element)
    {
      return parseInt(element.css("margin-top")) + parseInt(element.css("margin-bottom")) +
             parseInt(element.css("border-top-width")) + parseInt(element.css("border-bottom-width")) +
             parseInt(element.css("padding-top")) + parseInt(element.css("padding-bottom"));
    }

    function resize()
    {
      var textarea = content.find("textarea");
      var text = content.find(".text");
      var state = content.find("p.state");
      var message = content.find("p.message");
      var available = content.innerHeight();

      available -= parseInt(content.css("padding-top")) + parseInt(content.css("padding-bottom"));
      available -= totalAdditionalHeight(text);
      available -= totalAdditionalHeight(textarea);
      if (state.size())
        available -= state.height() + 10;
      available -= message.height();

      // Quirk to prevent vertical scrollbar in dialog client area when resizing it in chromium.
      available -= 3;

      textarea.height(available);
    }

    var operation = new Operation({ action: "determine review state change",
                                    url: "reviewstatechange",
                                    data: { review_id: review.id }});
    var result = operation.execute();
    var state_change = "";

    if (result)
      if (result.current_state == "open" && result.new_state == "accepted")
        state_change = "<p class='state' style='margin: 0; margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid black; font-weight: bold'>With these changes, the review will be ACCEPTED.</p>";
      else if (result.current_state == "accepted" && result.new_state == "open")
        state_change = "<p class='state' style='margin: 0; padding-bottom: 3px; border-bottom: 1px solid black; font-weight: bold'>With these changes, the review will NO LONGER be ACCEPTED.</p>";

    var content = $("<div class='comment' title='Submit Changes'>" + state_change + "<p class='message' style='margin: 0'>Additional note (optional):</p><div class='text'><textarea></textarea></div></div>");

    var buttons;

    buttons = {
                Submit: function () { if (finish(content.find("textarea").val())) { $(content).dialog("close"); location.reload(); } },
                Cancel: function () { $(content).dialog("close"); }
              };

    content.dialog({ width: 600, height: 250,
                     buttons: buttons,
                     resize: resize });

    resize();
  }

  Operation.whenIdle(start);
}

function cancelChanges()
{
  function finish()
  {
    var data = { review_id: review.id,
                 what: {} };

    if (0 != ((data.what["approval"] = approval.is(":checked")) +
              (data.what["comments"] = comments.is(":checked")) +
              (data.what["metacomments"] = metacomments.is(":checked"))))
    {
      var operation = new Operation({ action: "abort changes",
                                      url: "abortchanges",
                                      data: data });
      var result = operation.execute();

      if (result)
      {
        location.reload();

        if (result.profiling)
          console.log(result.profiling);
      }
      else
        return false;
    }

    return true;
  }

  var content = $("<div title='Warning!'><p><b>Aborted changes will be lost permanently.</b></p><legend><input type=checkbox id=what_approval checked>Abort reviewed/unreviewed changes</legend><legend><input type=checkbox id=what_comments checked>Abort written comments</legend><legend><input type=checkbox id=what_metacomments checked>Abort reopened/morphed comments</legend></div>");

  var approval = content.find("input#what_approval");
  var comments = content.find("input#what_comments");
  var metacomments = content.find("input#what_metacomments");

  content.find("legend").click(function (ev) { if (ev.target.nodeName.toLowerCase() != "input") $(ev.currentTarget).find("input").click(); });

  content.dialog({ width: 400, modal: true, buttons: { "Abort Changes": function () { if (finish()) content.dialog("close"); }, "Do Nothing": function () { content.dialog("close"); }}});
}

function closeReview()
{
  function proceed()
  {
    var operation = new Operation({ action: "close review",
                                    url: "closereview",
                                    data: { review_id: review.id }});

    if (operation.execute())
      location.reload();
  }

  var is_owner = false;

  for (var index = 0; index < review.owners.length; ++index)
  {
    if (user.id == review.owners[index].id)
    {
      is_owner = true;
      break;
    }
  }

  if (!is_owner)
  {
    var content = $("<div title=Please Confirm'><p><b>You are not the owner of this review.</b>  Are you sure you mean to close it?</p></div>");
    content.dialog({ width: 400, modal: true, buttons: { "Close Review": function () { content.dialog("close"); proceed(); }, "Do Nothing": function () { content.dialog("close"); }}});
  }
  else
    proceed();
}

function dropReview()
{
  function proceed()
  {
    var operation = new Operation({ action: "drop review",
                                    url: "dropreview",
                                    data: { review_id: review.id }});

    if (operation.execute())
      location.reload();
  }

  var content = $("<div title='Please Confirm'><p>Are you sure you mean to drop the review?</p></div>");
  content.dialog({ width: 400, modal: true, buttons: { "Drop Review": function () { content.dialog("close"); proceed(); }, "Do Nothing": function () { content.dialog("close"); }}});
}

function reopenReview()
{
  var operation = new Operation({ action: "reopen review",
                                  url: "reopenreview",
                                  data: { review_id: review.id }});

  if (operation.execute())
    location.reload();
}

function pingReview()
{
  function resize()
  {
    var textarea = content.find("textarea");
    var text = content.find(".text");
    var message = content.find("p");
    var available = content.innerHeight();

    available -= parseInt(content.css("padding-top")) + parseInt(content.css("padding-bottom"));
    available -= parseInt(text.css("margin-top")) + parseInt(text.css("padding-top")) + parseInt(text.css("padding-bottom")) + parseInt(text.css("margin-bottom"));
    available -= message.height();

    content.find("textarea").height(available);
  }

  var content = $("<div class='comment' title='Ping Review'><div class='text'><textarea></textarea></div></div>");

  function finish(type)
  {
    var operation = new Operation({ action: "ping review",
                                    url: "pingreview",
                                    data: { review_id: review.id,
                                            note: content.find("textarea").val() }});

    return operation.execute() != null;
  }

  var buttons = { "Send Ping": function () { if (finish()) { $(content).dialog("close"); } },
                  "Cancel": function () { $(content).dialog("close"); } };

  content.dialog({ width: 600, height: 250,
                   buttons: buttons,
                   closeOnEscape: false,
                   resize: resize });

  resize();
}

function editSummary()
{
  function finish(type)
  {
    var operation = new Operation({ action: "update review",
                                    url: "updatereview",
                                    data: { review_id: review.id,
                                            new_summary: content.find("input").val() }});

    return operation.execute() != null;
  }

  function checkFinished()
  {
    if (finish()) { $(content).dialog("close"); location.reload(); }
  }

  function handleKeypress(ev)
  {
    if (ev.keyCode == 13)
      checkFinished();
  }

  var content = $("<div class='comment' title='Edit Summary'><div class='text'>Enter new summary:<br><input></div></div>");

  content.find("input").val($("#summary").text());
  content.find("input").keypress(handleKeypress);

  var buttons = {
                  "Save": function () { checkFinished(); },
                  Cancel: function () { $(content).dialog("close"); }
                };

  content.dialog({ width: 600,
                   buttons: buttons });
}

function editDescription()
{
  function resize()
  {
    content.find("textarea").height(content.innerHeight() - 30);
  }

  function finish(type)
  {
    var operation = new Operation({ action: "update review",
                                    url: "updatereview",
                                    data: { review_id: review.id,
                                            new_description: content.find("textarea").val() }});

    return operation.execute() != null;
  }

  var self = this;
  var content = $("<div class='comment' title='Edit Description'><div class='text'><textarea rows=8></textarea></div></div>");

  content.find("textarea").val($("#description").text());

  var buttons = {
    Save: function () { if (finish()) { $(content).dialog("close"); location.reload(); } },
    Cancel: function () { $(content).dialog("close"); }
  };

  content.dialog({ width: 600,
                   buttons: buttons,
                   closeOnEscape: false,
                   resize: resize });
}

function editOwners()
{
  function finish(type)
  {
    var operation = new Operation({ action: "update review",
                                    url: "updatereview",
                                    data: { review_id: review.id,
                                            new_owners: content.find("input").val().split(/[,\s]+/g) }});

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

  var self = this;
  var content = $("<div class='editowner' title='Change Review Owner'><p>Please enter the user name(s) of the new review owner(s):<br><input></p></div>");

  content.find("input").val(owners.map(function (user) { return user.name; }).join(", "));
  content.find("input").keypress(handleKeypress);

  var buttons = {
    Save: function () { checkFinished(); },
    Cancel: function () { $(content).dialog("close"); }
  };

  content.dialog({ width: 400,
                   buttons: buttons });
}

$(document).ready(function ()
  {
    $("td.approve input").change(function (ev)
      {
        var target = $(ev.currentTarget);
        if (target.parents("td").hasClass("everything"))
        {
          markAllFiles(ev.currentTarget.checked ? "reviewed" : "pending");

          target.parents("table").find("td.approve.file input").each(function (index, element)
            {
              element.checked = ev.currentTarget.checked;
            });
        }
        else
        {
          var row = target.parents("tr");
          var file_id = parseInt(row.attr("critic-file-id"));
          var parent_index = target.attr("critic-parent-index");

          if (parent_index)
            parent_index = parseInt(parent_index);
          else
            parent_index = null;

          markFile(ev.currentTarget.checked ? "reviewed" : "pending", file_id, parent_index);
        }
      });

    if (typeof updateCheckInterval != "undefined" && updateCheckInterval)
      setTimeout(function ()
        {
          var callback = arguments.callee;
          $.ajax({ url: "checkserial?review=" + review.id + "&serial=" + review.serial + "&time=" + Date.now(),
                   dataType: "text",
                   success: function (data)
                     {
                       var match = /^current:(\d+)$/.exec(data);
                       if (match)
                       {
                         updateCheckInterval = parseInt(match[1]);

                         if (updateCheckInterval)
                           setTimeout(callback, updateCheckInterval * 1000);
                       }

                       if (data == "old")
                       {
                         var content = $("<div title='Review Updated'><p>The review has been updated since you loaded this page.  Would you like to reload?</p></div>");
                         content.dialog({ modal: true, buttons: { Reload: function () { content.dialog("close"); location.reload(); }, "Do Nothing": function () { content.dialog("close"); }}});
                       }
                     }});
        }, updateCheckInterval * 1000);
  });
