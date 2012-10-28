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

var anchorCommit = null, focusCommit = null, commitMarkers = null;

function CommitMarkers(commits)
{
  this.bothMarkers = $("<div class='marker left'></div><div class='marker right'></div>");

  $(document.body).append(this.bothMarkers);

  this.leftMarker = this.bothMarkers.first();
  this.rightMarker = this.bothMarkers.last();

  this.firstCommit = this.lastCommit = null;
  this.setCommits(commits);
}

CommitMarkers.prototype.setCommits = function (commits)
  {
    if (this.firstCommit)
      this.firstCommit.parent().removeClass("first");
    if (this.lastCommit)
      this.lastCommit.parent().removeClass("last");

    $("td.summary.selected").removeClass("selected");

    this.firstCommit = commits.first().children("td.summary");
    this.lastCommit = commits.last().children("td.summary");

    this.firstCommit.addClass("selected");
    this.lastCommit.addClass("selected");

    if (this.firstCommit.get(0) != this.lastCommit.get(0))
    {
      this.lastCommit.parent().addClass("last");
      this.firstCommit.parent().nextUntil("tr.commit.last").children("td.summary").addClass("selected");
      this.lastCommit.parent().removeClass("last");
    }

    this.updatePosition();
  };

CommitMarkers.prototype.updatePosition = function ()
  {
    var firstOffset = this.firstCommit.offset();
    var top = firstOffset.top - parseInt(this.firstCommit.css("padding-top"));
    var bottom = this.lastCommit.offset().top + this.lastCommit.height() + parseInt(this.lastCommit.css("padding-bottom"));

    this.leftMarker.offset({ top: top, left: firstOffset.left - parseInt(this.leftMarker.outerWidth()) - 1 });
    this.rightMarker.offset({ top: top, left: firstOffset.left + this.firstCommit.outerWidth() + 1 });

    this.bothMarkers.height(bottom - top + 2);
  };

CommitMarkers.prototype.remove = function ()
  {
    $("td.summary.selected").removeClass("selected");

    this.leftMarker.remove();
    this.rightMarker.remove();
  };

function rebase(name, base, newBaseBase, oldCount, newCount, baseOldCount, baseNewCount)
{
  function proceed()
  {
    var success = false;

    $.ajax({ async: false,
             url: "rebasebranch?repository=" + repository.id + "&name=" + name + "&base=" + base,
             dataType: "text",
             success: function (data)
               {
                 if (data == "ok")
                 {
                   $("button.perform").remove();
                   success = true;
                 }
                 else
                   reportError("update base branch", "Server reply: <i style='white-space: pre'>" + htmlify(data) + "</i>");
               },
             error: function ()
               {
                 reportError("update base branch", "Request failed.");
               }
           });

    return success;
  }

  var content = $("<div title=Please Confirm'><p>You are about to update Critic's record of the branch <b>" + htmlify(name) + "</b>.  It used to contain " + oldCount + " commits and will now contain these " + newCount + " commits instead.</p>" + (typeof baseOldCount == "number" ? "<p>In addition, the branch <b>" + htmlify(base) + "</b> will be modified to have <b>" + htmlify(newBaseBase) + "</b> as its new base branch instead of <b>" + htmlify(name) + "</b>, and will contain " + baseNewCount + " commits instead of " + baseOldCount + " commits.</p>" : "") + "<p><b>Note:</b> The git repository will not be affected at all by this.</p><p>Are you sure you want to do this?</p></div>");
  content.dialog({ width: 400, modal: true, buttons: { "Perform Rebase": function () { if (proceed()) content.dialog("close"); }, "Do Nothing": function () { content.dialog("close"); }}});
}

function showRelevantMerges(ev)
{
  $(ev.currentTarget).parents("table.log.relevant").find("tr.commit.merge").show();
  var text = ev.currentTarget.firstChild;
  text.nodeValue = text.nodeValue.replace("Show", "Hide");
  ev.currentTarget.onclick = hideRelevantMerges;
}

function hideRelevantMerges(ev)
{
  $(ev.currentTarget).parents("table.log.relevant").find("tr.commit.merge").hide();
  var text = ev.currentTarget.firstChild;
  text.nodeValue = text.nodeValue.replace("Hide", "Show");
  ev.currentTarget.onclick = showRelevantMerges;
}

var overrideShowSquashedDiff = null;

function resetSelection()
{
  if (anchorCommit && commitMarkers)
  {
    commitMarkers.remove();
    commitMarkers = null;
  }

  if (typeof automaticAnchorCommit == "string")
    anchorCommit = $("#" + automaticAnchorCommit);
  else
    anchorCommit = null;

  focusCommit = null;
}

function executeSelection(commit)
{
  if (anchorCommit && commitMarkers)
  {
    if (commit.size() && commit.get(0).parentNode == anchorCommit.get(0).parentNode)
    {
      var re_sha1 = /[0-9a-f]{8,40}(?=\?|$)/;

      var to_sha1 = re_sha1.exec($("td.summary.selected > a").first().attr("href"))[0]; //.parent("tr.commit").attr("id");
      var from_sha1 = re_sha1.exec($("td.summary.selected > a").last().attr("href"))[0]; //.parent("tr.commit").attr("id");

      if (overrideShowSquashedDiff)
        overrideShowSquashedDiff(from_sha1, to_sha1);
      else
        location.href = "showcommit?first=" + from_sha1 + "&last=" + to_sha1 + (typeof review != "undefined" && typeof review.id == "number" ? "&review=" + review.id : "");
    }

    resetSelection();
    return true;
  }

  return false;
}

$(document).ready(function ()
  {
    $("tr.commit td.summary").click(function (ev)
      {
        resetSelection();
      });

    $("tr.commit td.summary").mousedown(function (ev)
      {
        if (ev.button != 0 || ev.ctrlKey || ev.shiftKey || ev.altKey || ev.metaKey)
          return;

        if (!executeSelection($(ev.target).parents("tr.commit")))
        {
          anchorCommit = $(ev.currentTarget).parent("tr.commit");
          focusCommit = null;

          ev.preventDefault();
        }
      });

    $("tr.commit td.summary").mouseover(function (ev)
      {
        if (anchorCommit)
        {
          var commit = $(ev.currentTarget).parent("tr.commit");

          if (commit.size() && commit.get(0).parentNode == anchorCommit.get(0).parentNode)
            if (!commitMarkers)
            {
              if (commit.get(0) != anchorCommit.get(0))
              {
                focusCommit = commit;
                commitMarkers = new CommitMarkers(anchorCommit.add(focusCommit));
              }
            }
            else
            {
              if (commit.get(0) == anchorCommit.get(0))
              {
                commitMarkers.remove();
                commitMarkers = null;
              }
              else
              {
                focusCommit = commit;
                commitMarkers.setCommits(anchorCommit.add(focusCommit));
              }
            }

          if (commitMarkers)
            commitMarkers.updatePosition();
        }

        ev.stopPropagation();
      });

    $(document).mouseover(function (ev)
      {
        if (typeof automaticAnchorCommit == "string")
          resetSelection();
      });

    $(document).mouseup(function (ev)
      {
        executeSelection($(ev.target).parents("tr.commit"));
      });

    $("select.base").change(function (ev)
      {
        if (ev.target.value != "*")
          location.replace("log?repository=" + repository.id + "&branch=" + branch.name + "&base=" + ev.target.value);
      });

    $("span.squash, span.fixup").each(function (index, element)
      {
        var what = $(element).attr("class");
        $(element).tooltip({ fade: 250, bodyHandler: function () { return $("<div class='tooltip " + what + "'>" + (what == "fixup" ? "Fixup of" : "Squash into") + " <b>" + htmlify($(element).attr("critic-ref")) + "</b></div>"); }, showURL: false });
      });

    resetSelection();

    var highlight = $("tr.commit.highlight td");
    if (highlight.size())
      window.scrollTo(scrollX, highlight.offset().top - (innerHeight - highlight.height()) / 2);

    $("table.log.collapsable > thead.title").click(function (ev)
      {
        $(ev.currentTarget.parentNode).toggleClass("collapsed");
      });
  });
