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

var commentChainsPerFile = {};
var commentChainById = {};
var commentChains = [];

function Comment(id, author, time, state, text)
{
  this.id = id;
  this.author = author;
  this.time = time;
  this.state = state;
  this.text = text;
}

Comment.prototype.getLeader = function ()
  {
    var leader = htmlify(this.text.substr(0, 80));
    var linebreak = leader.indexOf("\n");

    if (linebreak != -1)
      leader = leader.substr(0, linebreak);

    var period = leader.indexOf(". ");

    if (period != -1)
      leader = leader.substr(0, period + 1);

    if (this.text.length > 80)
      leader += "&#8230;";

    return leader;
  };

function CommentLines(file, sha1, firstLine, lastLine)
{
  this.file = file;
  this.sha1 = sha1;
  this.firstLine = firstLine;
  this.lastLine = lastLine;
}

CommentLines.prototype.getFirstLine = function (chain)
  {
    for (var linenr = this.firstLine; linenr <= this.lastLine; ++linenr)
    {
      var base_id, line;

      if (this.file !== null)
      {
        var file = files[this.sha1];
        base_id = "f" + this.file + file.side + linenr;

        if (typeof file.parent == "number")
          base_id = "p" + file.parent + base_id;
        else if (window.selectedParent != null)
          base_id = "p" + selectedParent + base_id;
      }
      else
        base_id = "msg" + this.firstLine;

      line = document.getElementById("c" + chain.id + base_id);
      if (line)
        return line;

      line = document.getElementById(base_id);
      if (line)
        return line;
    }

    //console.log("first line missing: f" + this.file + files[this.sha1].side + this.firstLine);
    return null;
  };

CommentLines.prototype.getLastLine = function (chain)
  {
    for (var linenr = this.lastLine; linenr >= this.firstLine; --linenr)
    {
      var base_id, line;

      if (this.file !== null)
      {
        var file = files[this.sha1];
        base_id = "f" + this.file + file.side + linenr;

        if (typeof file.parent == "number")
          base_id = "p" + file.parent + base_id;
        else if (window.selectedParent != null)
          base_id = "p" + selectedParent + base_id;
      }
      else
        base_id = "msg" + this.lastLine;

      line = document.getElementById("c" + chain.id + base_id);
      if (line)
        return line;

      line = document.getElementById(base_id);
      if (line)
        return line;
    }

    //console.log("last line missing: f" + this.file + files[this.sha1].side + this.lastLine);
    return null;
  };

function CommentChain(id, user, type, type_is_draft, state, closed_by, addressed_by, comments, lines, markers)
{
  this.id = id;
  this.user = user;
  this.type = type;
  this.type_is_draft = type_is_draft;
  this.state = state;
  this.closed_by = closed_by;
  this.addressed_by = addressed_by;
  this.comments = comments;
  this.lines = lines;
  this.markers = markers || null;
}

CommentChain.extraButtons = {};

CommentChain.create = function (type_or_markers)
  {
    var chain_type = null;
    var markers = null;
    var paused = false;

    if (typeof type_or_markers == "string")
      chain_type = type_or_markers;
    else
      markers = type_or_markers;

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
      var message = content.find("p");
      var available = content.innerHeight();

      available -= parseInt(content.css("padding-top")) + parseInt(content.css("padding-bottom"));
      available -= totalAdditionalHeight(text);
      available -= totalAdditionalHeight(textarea);
      available -= message.height();

      // Quirk to prevent vertical scrollbar in dialog client area when resizing it in chromium.
      available -= 3;

      textarea.height(available);
    }

    var message = "";

    function abort()
    {
      markers.remove();
      currentMarkers = null;
    }

    var markersLocation;
    var useChangeset;
    var useFiles;

    if (markers)
    {
      var m1 = /(?:p(\d+))?f(\d+)([on])(\d+)/.exec(markers.firstLine.id);
      if (m1)
      {
        var side = m1[3];
        var parent;

        if (m1[1] !== undefined)
        {
          parent = parseInt(m1[1]);
          useChangeset = changeset[parent];
          useFiles = files[parent];
        }
        else
        {
          useChangeset = changeset;
          useFiles = files;
        }

        var file = parseInt(m1[2]);
        var sha1 = side == 'o' ? useFiles[file].old_sha1 : useFiles[file].new_sha1;
        var firstLine = parseInt(m1[4]);
        var m2 = /(?:p\d+)?f\d+[on](\d+)/.exec(markers.lastLine.id);
        var lastLine = parseInt(m2[1]);

        if (side == 'o' && markers.linesModified())
        {
          message = "<p style='margin: 0'>"
                  +   "<b>Warning:</b> An issue raised against the old version of "
                  +   "modified lines will never be marked as addressed, and "
                  +   "will thus need to be resolved manually."
                  + "</p>";
        }
        else
        {
          var data = { review_id: review.id,
                       origin: side == 'o' ? "old" : "new",
                       parent_id: useChangeset.parent.id,
                       child_id: useChangeset.child.id,
                       file_id: file,
                       offset: firstLine,
                       count: lastLine + 1 - firstLine };

          var operation = new Operation({ action: "validate commented lines",
                                          url: "validatecommentchain",
                                          data: data });
          var result = operation.execute();

          if (result.verdict == "modified")
          {
            var content = $("<div title='Warning!'>"
                          +   "<p>"
                          +     "One or more of the lines you are commenting are modified by a "
                          +       "<a href='/" + result.parent_sha1 + ".." + result.child_sha1 + "?review=" + review.id + "#f" + file + "o" + result.offset + "'>later commit</a> "
                          +     "in this review."
                          +   "</p>"
                          +   "<p>"
                          +     "An issue raised against already modified lines "
                          +     "will never be marked as addressed, and will thus "
                          +     "need to be resolved manually."
                          +   "</p>"
                          + "</div>");

            content.dialog({ modal: true, width: 400,
                             buttons: { "Comment Anyway": function () { content.dialog("close"); start(); },
                                        "Cancel": function () { content.dialog("close"); abort(); }}
                           });

            paused = true;
          }
          else if (result.verdict == "transferred")
          {
            message = "<p style='margin: 0'>"
                    +   "<b>Note:</b> This file is modified by "
                    +     (result.count > 1 ? result.count + " later commits " : "a later commit ")
                    +   "in this review, without affecting the commented lines.  "
                    +   "This comment will appear against each version of the file."
                    + "</p>";
          }
          else if (result.verdict == "invalid")
          {
            var content = $("<div title='Error!'>"
                          +   "<p>"
                          +     "<b>It is not possible to comment these lines.</b>"
                          +   "</p>"
                          +   "<p>"
                          +     "This is probably because this/these commits are not part of the review."
                          +   "</p>"
                          + "</div>");

            content.dialog({ modal: true,
                             buttons: { "OK": function () { content.dialog("close"); }}
                           });

            abort();
            return;
          }
        }

        markersLocation = "file";
      }
      else
      {
        var m1 = /msg(\d+)/.exec(markers.firstLine.id);
        firstLine = parseInt(m1[1]);
        var m2 = /msg(\d+)/.exec(markers.lastLine.id);
        lastLine = parseInt(m2[1]);

        if ("child" in changeset)
          useChangeset = changeset;
        else
          useChangeset = changeset[0];

        markersLocation = "commit";
      }
    }

    var content;

    function finish(chain_type)
    {
      var text = content.find("textarea").val();
      var data = { review_id: review.id,
                   chain_type: chain_type,
                   text: text };

      if (markers)
      {
        if (markersLocation == "file")
        {
          data.file_context = { origin: side == 'o' ? "old" : "new",
                                file_id: file,
                                child_id: useChangeset.child.id,
                                old_sha1: useFiles[file].old_sha1,
                                new_sha1: useFiles[file].new_sha1,
                                offset: firstLine,
                                count: lastLine + 1 - firstLine };

          if (useChangeset.parent)
            data.file_context.parent_id = useChangeset.parent.id;
        }
        else
          data.commit_context = { commit_id: useChangeset.child.id,
                                  offset: firstLine,
                                  count: lastLine + 1 - firstLine };
      }

      var operation = new Operation({ action: "create comment",
                                      url: "createcommentchain",
                                      data: data });
      var result = operation.execute();

      if (result.status == "ok")
      {
        var comment = new Comment(result.comment_id, user, "now", "draft", text);

        if (markers)
        {
          var lines = new CommentLines(file, sha1, firstLine, lastLine);
          var chain = new CommentChain(result.chain_id, user, chain_type, false, "draft", null, null, [comment], lines, markers);

          markers.commentChain = chain;
          commentChains.push(chain);

          if (!(file in commentChainsPerFile))
            commentChainsPerFile[file] = [];

          commentChainsPerFile[file].push(markers.commentChain);

          markers.setType(chain_type);
        }
        else
        {
          var chain = new CommentChain(result.chain_id, user, chain_type, false, "draft", null, null, [comment], null, null);

          var html = "<tr class='comment draft " + chain_type + "'><td class='author'>" + htmlify(user.displayName) + "</td><td class='title'><a href='/showcomment?chain=" + chain.id + "'>" + chain.comments[0].getLeader() + "</a></td><td class='when'>now</td></tr>";
          if (chain_type == "issue")
          {
            target = $("tr#draft-issues");
            if (target.length == 0)
              $("table.comments tr.h1").after("<tr id='draft-issues'><td class='h2' colspan='3'><h2>Draft Issues<a href='/showcomments?review=" + review.id + "&amp;filter=draft-issues'>[display all]</h2></td></tr>" + html);
            else
              target.after(html);
          }
          else
          {
            target = $("tr#draft-notes");
            if (target.length == 0)
            {
              target = $("tr#notes");
              if (target.length == 0)
                target = $("tr.buttons");
              target.before("<tr id='draft-notes'><td class='h2' colspan='3'><h2>Draft Notes<a href='/showcomments?review=" + review.id + "&amp;filter=draft-notes'>[display all]</h2></td></tr>" + html);
            }
            else
              target.after(html);
          }

          /* Force "compatible history navigation" from now on. */
          unload = function () {}
        }

        updateDraftStatus(result.draft_status);

        return true;
      }

      return success;
    }

    function start()
    {
      content = $("<div class='comment' title='Create Comment'>" + message + "<div class='text'><textarea></textarea></div></div>");

      var buttons;

      if (chain_type != null)
        buttons = { Save: function () { if (finish(chain_type)) { content.dialog("close"); } } };
      else
      {
        buttons = { "Add issue": function () { if (finish("issue")) { markers = null; content.dialog("close"); } },
                    "Add note": function () { if (finish("note")) { markers = null; content.dialog("close"); } } };

        function wrapDialogFunction(fn)
        {
          return function () { if (fn()) content.dialog("close"); };
        }

        for (var title in CommentChain.extraButtons)
          buttons[title] = wrapDialogFunction(CommentChain.extraButtons[title]);
      }

      var data = {};
      if (markers)
      {
        data.context = markersLocation;

        if (markersLocation == "file")
        {
          data.changeset = useChangeset.id;
          data.path = useFiles[file].path;
          data.sha1 = useFiles[file][side == "o" ? "old_sha1" : "new_sha1"];
          data.lineIndex = firstLine - 1;
        }
        else
        {
          data.sha1 = useChangeset.child.sha1;
          data.lineIndex = firstLine;
        }

        data.lineCount = lastLine - firstLine + 1;
      }
      else
        data.context = "general";

      var hook_results = hooks["create-comment"].map(function (callback) { try { return callback(data); } catch (e) { return []; } });

      for (var index1 = 0; index1 < hook_results.length; ++index1)
      {
        var hook_result = hook_results[index1];

        if (hook_result)
          for (var index2 = 0; index2 < hook_result.length; ++index2)
          {
            (function (hooked)
             {
               if (hooked.href)
                 buttons[hooked.title] = function () { content.dialog("close"); location.href = hooked.href; };
               else
                 buttons[hooked.title] = function () { if (hooked.callback(content.find("textarea").val())) content.dialog("close"); };
             })(hook_result[index2]);
          }
      }

      buttons["Cancel"] = function () { content.dialog("close");  };

      function close()
      {
        if (markers && chain_type == null)
          markers.remove();

        currentMarkers = null;
      }

      content.dialog({ width: 600, height: 250,
                       buttons: buttons,
                       closeOnEscape: false,
                       resize: resize,
                       close: close });

      resize();
    }

    if (!paused)
      start();
  };

CommentChain.prototype.getFirstLine = function ()
  {
    return this.lines.getFirstLine(this);
  };

CommentChain.prototype.getLastLine = function ()
  {
    return this.lines.getLastLine(this);
  };

CommentChain.prototype.removeDraftStatus = function ()
  {
    if (this.state == "draft")
    {
      this.state = "open";

      var comment = this.comments[this.comments.length - 1];
      if (comment.state == "draft")
        comment.state = "current";
    }
  };

CommentChain.currentDialog = null;
CommentChain.reopening = null;

CommentChain.prototype.display = function ()
  {
    if (CommentChain.currentDialog)
    {
      CommentChain.currentDialog.dialog("close");
      CommentChain.currentDialog = null;
    }

    var self = this;
    var html = "<div class='comment-dialog' title='" + (this.type == "issue" ? "Issue raised" : "Note") + " by " + htmlify(this.comments[0].author.displayName) + "'>";

    for (var index = 0; index < this.comments.length; ++index)
    {
      var comment = this.comments[index];
      html += "<div class='comment" + (comment.state == "draft" ? " draft" : "") + "'><div class='header'><span class='author'>" + htmlify(comment.author.displayName) + "</span> posted <span class='time'>" + comment.time + "</span></div><div class='text'>" + htmlify(comment.text) + "</div></div>";
    }

    if (this.state != "draft" && this.state != "open")
    {
      var text;

      switch (this.state)
      {
      case "addressed":
        text = "Addressed by <a href='/showcommit?review=" + review.id + "&amp;sha1=" + this.addressed_by + "'>" + this.addressed_by.substr(0, 8) + "</a>";
        break;

      case "closed":
        text = "Resolved by " + htmlify(this.closed_by.displayName);
        break;
      }

      html += "<div class='resolution'>" + text + "</div>";
    }

    html += "</div>";

    var content = $(html);
    var buttons = {};

    if (this.state == "draft" || comment.state == "draft")
    {
      buttons["Edit"] = function () { self.editComment(comment, content); };
      buttons["Delete"] = function () { self.deleteComment(comment, content); };
    }
    else
      buttons["Reply"] = function () { self.reply(content); };

    if (this.state == "closed" || this.addressed_by)
      buttons["Reopen issue"] = function () { content.dialog("close"); self.reopen(); };

    var back = this.type_is_draft ? "back " : "";

    if (this.type == "issue")
    {
      if (this.state == "open" && !this.type_is_draft)
        buttons["Resolve issue"] = function () { self.resolve(content); };

      if (back || user.options.ui.convertIssueToNote)
        buttons["Convert " + back + "to note"] = function () { self.morph(content); };
    }
    else
      buttons["Convert " + back + "to issue"] = function () { self.morph(content); };

    var data = {};
    if (this.markers)
    {
      var m1 = /(?:p(\d+))?f(\d+)([on])(\d+)/.exec(this.markers.firstLine.id);
      var m2 = /(?:p\d+)?f\d+[on](\d+)/.exec(this.markers.lastLine.id);
      if (m1 && m2)
      {
        var side = m1[3];

        if (m1[1] !== undefined)
        {
          var parent = parseInt(m1[1]);
          useChangeset = changeset[parent];
          useFiles = files[parent];
        }
        else
        {
          useChangeset = changeset;
          useFiles = files;
        }

        var file = parseInt(m1[2]);

        data.context = "file";
        data.changeset = useChangeset.id;
        data.path = useFiles[file].path;
        data.sha1 = useFiles[file][side == "o" ? "old_sha1" : "new_sha1"];
        data.lineIndex = parseInt(m1[4]) - 1;
        data.lineCount = parseInt(m2[1]) - data.lineIndex;
      }
      else
      {
        var m1 = /msg(\d+)/.exec(this.markers.firstLine.id);
        var m2 = /msg(\d+)/.exec(this.markers.lastLine.id);

        data.context = "commit";
        data.sha1 = ("child" in changeset) ? changeset.child.sha1 : changeset[0].child.sha1;
        data.lineIndex = parseInt(m1[1]);
        data.lineCount = parseInt(m2[1]) - data.lineIndex + 1;
      }
    }
    else
      data.context = "general";

    var hook_results = hooks["display-comment"].map(function (callback) { try { return callback(data); } catch (e) { return []; } });

    for (var index1 = 0; index1 < hook_results.length; ++index1)
    {
      var hook_result = hook_results[index1];

      if (hook_result)
        for (var index2 = 0; index2 < hook_result.length; ++index2)
        {
          (function (hooked)
           {
             if (hooked.href)
               buttons[hooked.title] = function () { content.dialog("close"); location.href = hooked.href; };
             else
               buttons[hooked.title] = function () { if (hooked.callback(content.find("textarea").val())) content.dialog("close"); };
           })(hook_result[index2]);
        }
    }

    buttons["Close"] = function () { content.dialog("close"); };

    content.dialog({ width: 600, buttons: buttons, close: function () { CommentChain.currentDialog = null; }});

    if (content.closest(".ui-dialog").height() > innerHeight)
      content.dialog("option", "height", innerHeight - 10);

    CommentChain.currentDialog = content;
  };

CommentChain.prototype.reply = function (parentDialog)
  {
    var self = this;
    var content = $("<div class='comment' title='Write Reply'><div class='text'><textarea></textarea></div></div>");

    function resize()
    {
      content.find("textarea").height(content.innerHeight() - 30);
    }

    function finish()
    {
      var text = content.find("textarea").val();
      var data = { chain_id: self.id,
                   text: text };
      var success = false;

      var operation = new Operation({ action: "add reply",
                                      url: "createcomment",
                                      data: data });
      var result = operation.execute();

      if (result)
      {
        var comment = new Comment(result.comment_id, user, "now", "draft", text);
        self.comments.push(comment);

        var container = $("div.comment-chain#c" + self.id);
        if (container.length)
        {
          var buttons = container.find("div.comments").find("div.buttons");
          var resolution = container.find("div.comments").find("div.resolution");
          var target = resolution.size() ? resolution : buttons;

          target.before("<div class='comment draft' id='c" + self.id + "c" + comment.id + "'>" +
                          "<div class='header'><span class='author'>" + htmlify(user.displayName) + "</span> posted <span class='time'>now</span></div>" +
                          "<div class='text' id='c" + comment.id + "text'>" + htmlify(text) + "</div>" +
                        "</div>");
          buttons.children("button.reply").addClass("hidden").before("<button class='edit'>Edit</button><button class='delete'>Delete</button>");
          buttons.children("button.edit").button().click(function () { self.editComment(comment, null); });
          buttons.children("button.delete").button().click(function () { self.deleteComment(comment, null); });

          CommentMarkers.updateAll();
        }

        updateDraftStatus(result.draft_status);
        return true;
      }
      else
        return false;
    }

    content.dialog({ width: 600, height: 250,
                     buttons: { Save: function () { if (finish()) { content.dialog("close"); if (parentDialog) parentDialog.dialog("close"); } },
                                Cancel: function () { content.dialog("close"); }},
                     closeOnEscape: false,
                     resize: resize,
                     modal: true });

    resize();
  };

CommentChain.prototype.reopen = function (from_showcomment, from_onload)
  {
    var self = this;
    var content;

    function cancel()
    {
      content.dialog("close");
      CommentChain.reopening = null;
    }

    function finish(markers)
    {
      var operation;

      if (markers)
      {
        var m1 = /(?:p(\d+))?f(\d+)[on](\d+)/.exec(markers.firstLine.id);

        var useFiles;
        if (m1[1] !== undefined)
          useFiles = files[parseInt(m1[1])];
        else
          useFiles = files;

        var file = parseInt(m1[2]);
        var sha1 = useFiles[file].new_sha1;
        var firstLine = parseInt(m1[3]);
        var m2 = /(?:p\d+)?f\d+[on](\d+)/.exec(markers.lastLine.id);
        var lastLine = parseInt(m2[1]);

        operation = new Operation({ action: "reopen issue",
                                    url: "reopenaddressedcommentchain",
                                    data: { chain_id: self.id,
                                            commit_id: changeset.child.id,
                                            sha1: sha1,
                                            offset: firstLine,
                                            count: lastLine + 1 - firstLine }});
      }
      else
        operation = new Operation({ action: "reopen issue",
                                    url: "reopenresolvedcommentchain",
                                    data: { chain_id: self.id }});

      var result = operation.execute();

      if (result)
      {
        if (result.new_state == "open")
        {
          self.state = "open";

          if (markers)
          {
            self.markers.setType(self.type, self.state);

            self.lines.sha1 = sha1;
            self.lines.firstLine = firstLine;
            self.lines.lastLine = lastLine;

            self.markers.updatePosition();
          }
        }
        else
        {
          showMessage("Reopen Issue",
                      "Issue still addressed!",
                      "The issue was successfully transferred to the selected lines, " +
                      "but those lines were in turn modified by a later commit in the " +
                      "review, so the issue is still marked as addressed.");
        }

        updateDraftStatus(result.draft_status);

        var container = $("div.comment-chain#c" + self.id);
        if (container.length)
        {
          container.find("div.resolution").remove();
          CommentMarkers.updateAll();
        }
      }

      markers.remove();
      cancel();
    }

    if (this.addressed_by)
    {
      if (from_showcomment || changeset.child.sha1 != this.addressed_by)
      {
        content = $("<div title='Reopen Issue'>Addressed issues can only be reopened from a regular diff of the commit that addressed the issue.  Would you like to go there?</div>");

        function goThere()
        {
          content.dialog("close");
          location.href = "/showcommit?review=" + review.id + "&sha1=" + self.addressed_by + "&reopen=" + self.id;
        }

        function stayHere()
        {
          content.dialog("close");
        }

        content.dialog({ width: 600,
                         buttons: { "Yes, go there": goThere, "No, stay here": stayHere },
                         resizable: false });
      }
      else
      {
        this.finish = finish;

        content = $("<div title='Reopen Issue'>Please select the lines in the new version of the file where the comment should be transferred to.</div>");

        content.dialog({ width: 800,
                         position: "top",
                         buttons: { Cancel: cancel },
                         resizable: false });

        CommentChain.reopening = this;
      }
    }
    else if (this.state == "closed")
      finish(null);
  };

CommentChain.prototype.resolve = function (dialog)
  {
    var self = this;

    function finish()
    {
      var operation = new Operation({ action: "resolve issue",
                                      url: "resolvecommentchain",
                                      data: { chain_id: self.id }});
      var result = operation.execute();

      if (result)
      {
        self.state = 'closed';
        self.closed_by = user;

        if (self.markers)
          self.markers.setType(self.type, self.state);

        var container = $("#c" + self.id);
        if (container.length)
        {
          container.find("div.buttons").before("<div class='resolution'>Resolved by " + htmlify(user.displayName) + "</div>");
          container.find("button.resolve").remove();

          CommentMarkers.updateAll();
        }

        updateDraftStatus(result.draft_status);

        if (dialog)
          dialog.dialog("close");
      }
    }

    if (user.options.ui.resolveIssueWarning && user.id != this.user.id)
    {
      var content = $("<div title='Please Confirm'><p><b>You did not raise this issue.</b>  Are you sure you mean to resolve it explicitly?</p><p>If you fixed the code, you should push a commit with the fixes, which often closes the issue automatically.  And even if it does not, you may want to let the reviewer who raised the issue resolve it after reviewing your fix.</p></div>");
      content.dialog({ width: 400, modal: true, buttons: { "Resolve issue": function () { content.dialog("close"); finish(); }, "Do nothing": function () { content.dialog("close"); }}});
    }
    else
      finish();
  };

CommentChain.prototype.morph = function (dialog, button)
  {
    var self = this;
    var new_type = this.type == 'issue' ? 'note' : 'issue';

    var operation = new Operation({ action: "change comment type",
                                    url: "morphcommentchain",
                                    data: { chain_id: this.id,
                                            new_type: new_type }});
    var result = operation.execute();

    if (result)
    {
      self.type = new_type;

      if (self.markers)
        self.markers.setType(self.type, self.state);

      var title = $("#c" + self.id + " .comment-chain-title");

      if (new_type == 'note')
        title.text(title.text().replace("Issue raised by", "Note by"));
      else
        title.text(title.text().replace("Note by", "Issue raised by"));

      self.type_is_draft = !self.type_is_draft;

      var back = self.type_is_draft ? "back " : "";

      if (button)
        if (new_type == 'note')
          $(button).button("option", "label", "Convert " + back + "to issue");
        else if (back || user.options.ui.convertIssueToNote)
          $(button).button("option", "label", "Convert " + back + "to note");

      updateDraftStatus(result.draft_status);

      if (dialog)
        dialog.dialog("close");
    }
  };

CommentChain.prototype.editComment = function (comment, parentDialog)
  {
    var self = this;
    var content = $("<div class='comment' title='Edit Comment'><div class='text'><textarea>" + htmlify(comment.text) + "</textarea></div></div>");

    function resize()
    {
      content.find("textarea").height(content.innerHeight() - 30);
    }

    function finish()
    {
      var new_text = content.find("textarea").val();

      var operation = new Operation({ action: "update comment",
                                      url: "updatecomment",
                                      data: { comment_id: comment.id,
                                              new_text: new_text }});
      var result = operation.execute();

      if (result)
      {
        comment.text = new_text;

        $("#c" + comment.id + "text").text(new_text);

        updateDraftStatus(result.draft_status);
        return true;
      }
      else
        return false;
    }

    content.dialog({ width: 600, height: 250,
                     buttons: { Save: function () { if (finish()) { content.dialog("close"); if (parentDialog) parentDialog.dialog("close"); } },
                                Cancel: function () { content.dialog("close"); }},
                     closeOnEscape: false,
                     resize: resize,
                     modal: true });

    resize();
  };

CommentChain.prototype.deleteComment = function (comment, parentDialog)
  {
    var self = this;
    var content = $("<div class='dialog' title='Delete Comment'?>Are you sure?</div>");

    function finish()
    {
      var operation = new Operation({ action: "delete comment",
                                      url: "deletecomment",
                                      data: { comment_id: comment.id }});
      var result = operation.execute();

      if (result)
      {
        self.comments.pop();

        if (self.comments.length == 0)
          if (self.markers)
          {
            commentChains.splice(commentChains.indexOf(self), 1);
            commentChainsPerFile[self.lines.file].splice(commentChainsPerFile[self.lines.file].indexOf(self), 1);
            self.markers.remove();
          }
          else
          {
            $("#c" + self.id).remove();
            if ($("table.file").length == 0)
              location.href = "/showreview?id=" + review.id;
          }
        else
        {
          $("#c" + self.id + "c" + comment.id).remove();

          var buttons = $("#c" + self.id + " div.buttons");
          buttons.children("button.edit, button.delete").remove();
          buttons.children("button.reply").removeClass("hidden");
        }

        updateDraftStatus(result.draft_status);
        return true;
      }
      else
        return false;
    }

    content.dialog({ modal: true,
                     buttons: { Delete: function () { content.dialog("close"); if (finish() && parentDialog) { parentDialog.dialog("close"); } },
                                Cancel: function () { content.dialog("close"); }}});
  };

CommentChain.prototype.toolTip = function ()
  {
    var html = "<div class='tooltip'>";
    html += "<div class='header'>" + (this.type == "issue" ? "Issue raised" : "Note") + " by " + htmlify(this.comments[0].author.displayName) + "</div>";
    html += "<div class='text sourcefont'>" + htmlify(this.comments[0].text) + "</div>";
    html += "</div>";
    return html;
  };

CommentChain.removeAll = function ()
  {
    if (typeof commentChains != "undefined")
    {
      for (var index = 0; index < commentChains.length; ++index)
        commentChains[index].markers.remove();

      commentChains = [];
    }
  };

function CommentMarkers(commentChain)
{
  var self = this;

  allMarkers.push(this);

  if (this.commentChain = commentChain)
  {
    this.firstLine = commentChain.getFirstLine();
    this.lastLine = commentChain.getLastLine();
  }
  else
    this.firstLine = this.lastLine = null;

  this.bothMarkers = $("<div class='marker left'></div><div class='marker right'></div>");
  this.leftMarker = this.bothMarkers.first();
  this.rightMarker = this.bothMarkers.last();

  if (commentChain)
    this.setType(commentChain.type, commentChain.state);
  else
    this.setType("new");

  this.bothMarkers.tooltip({
    content: function () { if (self.commentChain) return self.commentChain.toolTip() },
    items: "div.marker",
    tooltipClass: "comment-tooltip",
    track: true,
    hide: false
  });

  this.leftMarker.click(function () { if (self.commentChain) self.commentChain.display(); });
  this.rightMarker.click(function () { if (self.commentChain) self.commentChain.display(); });

  $(document.body).append(this.bothMarkers);

  this.updatePosition();
}

CommentMarkers.prototype.setLines = function (firstLine, lastLine)
{
  this.firstLine = firstLine;
  this.lastLine = lastLine;
  this.updatePosition();
}

CommentMarkers.prototype.setType = function (type, state)
{
  this.bothMarkers.removeClass("issue note new open addressed closed");
  this.bothMarkers.addClass(type);

  if (type == "issue" && typeof state != "undefined")
    this.bothMarkers.addClass(state);
}

CommentMarkers.prototype.updatePosition = function ()
  {
    if (this.commentChain)
    {
      this.firstLine = this.commentChain.getFirstLine();
      this.lastLine = this.commentChain.getLastLine();
    }

    if (this.firstLine)
    {
      var firstLine = $(this.firstLine);
      var lastLine = $(this.lastLine);

      if (firstLine.parents("table.file").is(".show.expanded") ||
          firstLine.parents("table.commit-msg").size())
      {
        this.leftMarker.css("display", "block");
        this.rightMarker.css("display", "block");

        var top = firstLine.offset().top - 2;
        var bottom = lastLine.offset().top + lastLine.height();

        if (firstLine.hasClass("whole"))
        {
          var linenr = firstLine.prevAll("td.linenr.old");
          this.leftMarker.offset({ top: top, left: linenr.offset().left - this.leftMarker.width() - 4 });
        }
        else if (firstLine.hasClass("old") || firstLine.hasClass("single") && !firstLine.hasClass("commit-msg"))
        {
          var edge = firstLine.prevAll("td.edge");
          this.leftMarker.offset({ top: top, left: edge.offset().left + edge.width() - this.leftMarker.width() - 4 });
        }
        else
          this.leftMarker.offset({ top: top, left: firstLine.offset().left - this.leftMarker.width() - 6 });

        if (firstLine.hasClass("new") || firstLine.hasClass("single"))
          this.rightMarker.offset({ top: top, left: firstLine.nextAll("td.edge").offset().left });
        else
          this.rightMarker.offset({ top: top, left: firstLine.nextAll("td.middle").offset().left + 2 });

        this.leftMarker.height(bottom - top - 1);
        this.rightMarker.height(bottom - top - 1);

        return;
      }
    }

    this.leftMarker.css("display", "none");
    this.rightMarker.css("display", "none");
  };

CommentMarkers.prototype.remove = function ()
  {
    this.leftMarker.remove();
    this.rightMarker.remove();

    allMarkers.splice(allMarkers.indexOf(this), 1);
  };

CommentMarkers.prototype.linesModified = function ()
  {
    var iter = $(this.firstLine).closest("tr");
    var stop = $(this.lastLine).closest("tr");

    do
    {
      if (!iter.hasClass("context"))
        return true;

      if (iter.is(stop))
        break;

      iter = iter.next("tr");
    }
    while (iter.size());

    return false;
  };

CommentMarkers.updateAll = function ()
{
  try
  {
    for (var index = 0; index < allMarkers.length; ++index)
      allMarkers[index].updatePosition();
  }
  catch (e)
  {
  }
}

var activeMarkers = null, anchorLine = null, currentMarkers = null, allMarkers = [];

function startCommentMarking(ev)
{
  if (ev.ctrlKey || ev.shiftKey || ev.altKey || ev.metaKey || /showcomments?$/.test(location.pathname) || ev.button != 0)
    return;

  if (ev.currentTarget.id && !activeMarkers && !currentMarkers)
  {
    if (CommentChain.reopening && CommentChain.reopening.lines.file != $(ev.currentTarget).parents("table.file").first().attr("critic-file-id"))
    {
      showMessage("Not supported", "Not supported", "Reopening an issue against lines in a different file is not supported.");
      return;
    }

    anchorLine = ev.currentTarget;
    activeMarkers = new CommentMarkers;
    activeMarkers.setLines(anchorLine, anchorLine);

    ev.preventDefault();
  }
}

function continueCommentMarking(ev)
{
  if (activeMarkers && ev.currentTarget.id)
    if (ev.currentTarget.parentNode.parentNode == activeMarkers.firstLine.parentNode.parentNode && ev.currentTarget.cellIndex == anchorLine.cellIndex)
    {
      var firstLine, lastLine;

      if (ev.currentTarget.parentNode.sectionRowIndex < anchorLine.parentNode.sectionRowIndex)
      {
        firstLine = ev.currentTarget;
        lastLine = anchorLine;
      }
      else
      {
        firstLine = anchorLine;
        lastLine = ev.currentTarget;
      }

      activeMarkers.setLines(firstLine, lastLine);
    }
}

/* This function is overridden on some pages. */
function handleMarkedLines(markers)
{
  CommentChain.create(markers);
}

function endCommentMarking(ev)
{
  if (activeMarkers)
  {
    if (CommentChain.reopening)
      CommentChain.reopening.finish(activeMarkers);
    else
    {
      currentMarkers = activeMarkers;
      handleMarkedLines(activeMarkers);
    }

    activeMarkers = null;
    ev.preventDefault();
  }
}

function markChainsAsRead(chain_ids)
{
  var operation = new Operation({ action: "mark comments as read",
                                  url: "markchainsasread",
                                  data: { chain_ids: chain_ids },
                                  callback: function () {} });

  operation.execute();
}

$(document).ready(function ()
  {
    if (typeof commentChains != "undefined")
      $.each(commentChains, function (index, commentChain)
        {
          try
          {
            if (commentChain.lines.file !== null)
            {
              if (!(commentChain.lines.file in commentChainsPerFile))
                commentChainsPerFile[commentChain.lines.file] = [];
              commentChainsPerFile[commentChain.lines.file].push(commentChain);
            }

            commentChain.markers = new CommentMarkers(commentChain);
          }
          catch (e)
          {
            //console.log(e);
          }
        });

    if (typeof review != "undefined")
      $("td.line")
        .mousedown(startCommentMarking)
        .mouseover(continueCommentMarking)
        .mouseup(endCommentMarking);

    CommentMarkers.updateAll();
  });

$(window).load(function ()
  {
    CommentMarkers.updateAll();

    var match = /(?:\?|&)reopen=(\d+)(?:&|$)/.exec(location.search);
    if (match)
    {
      for (var index in commentChains)
        if (commentChains[index].id == match[1])
        {
          var chain = commentChains[index];
          var file_id = chain.lines.file;

          expandFile(file_id);

          var first_line = $(chain.markers.firstLine);
          var last_line = $(chain.markers.lastLine);

          scrollTo(0, first_line.offset().top - innerHeight / 2 + (last_line.offset().top + last_line.height() - first_line.offset().top) / 2);

          setTimeout(function () { chain.reopen(false, true); }, 10);
        }
    }
  });

onresize = function ()
  {
    CommentMarkers.updateAll();
  };
