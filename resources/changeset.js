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

var files = [];
var blocks = [];

function makeLine(fileId, oldOffset, oldLine, newLine, newOffset)
{
  var row = document.createElement('tr');
  row.className = 'line context';
  row.id = 'f' + fileId + 'o' + oldOffset + 'n' + newOffset;

  var edge1 = row.insertCell(-1);
  edge1.className = 'edge';
  var oldOffsetCell = row.insertCell(-1);
  oldOffsetCell.textContent = oldOffset;
  oldOffsetCell.className = 'linenr old';
  oldOffsetCell.align = 'right';
  var oldLineCell = row.insertCell(-1);
  oldLineCell.innerHTML = oldLine ? oldLine : "&nbsp;";
  oldLineCell.className = 'line old';
  oldLineCell.id = 'f' + fileId + 'o' + oldOffset;
  var middle = row.insertCell(-1);
  middle.innerHTML = '&nbsp;';
  middle.className = 'middle';
  middle.colSpan = 2;
  var newLineCell = row.insertCell(-1);
  newLineCell.innerHTML = newLine ? newLine : "&nbsp;";
  newLineCell.className = 'line new';
  newLineCell.id = 'f' + fileId + 'n' + newOffset;
  var newOffsetCell = row.insertCell(-1);
  newOffsetCell.textContent = newOffset;
  newOffsetCell.className = 'linenr new';
  var edge2 = row.insertCell(-1);
  edge2.className = 'edge';

  if (typeof startCommentMarking != "undefined")
  {
    var lineCells = $(row).children("td.line");
    lineCells.mousedown(startCommentMarking);
    lineCells.mouseover(continueCommentMarking);
    lineCells.mouseup(endCommentMarking);
  }

  return row;
}

function previousTableSection(node)
{
  while (node.parentNode.nodeName.toLowerCase() != "table")
    node = node.parentNode;
  do
    node = node.previousSibling;
  while (node.nodeName.toLowerCase() != "tbody");
  return node;
}

function nextTableSection(node)
{
  while (node.parentNode.nodeName.toLowerCase() != "table")
    node = node.parentNode;
  do
    node = node.nextSibling;
  while (node.nodeName.toLowerCase() != "tbody");
  return node;
}

function hasClass(element, cls)
{
  return new RegExp("(^|\\s)" + cls + "($|\\s)").test(element.className)
}
function addClass(element, cls)
{
  if (!hasClass(element, cls))
    element.className += " " + cls;
}
function removeClass(element, cls)
{
  if (hasClass(element, cls))
    element.className = element.className.replace(new RegExp("(^|\\s+)" + cls + "($|(?=\\s))"), "");
}

var expandedFiles = {};
var extractedFiles = {};

var CONTEXT    = 1;
var DELETED    = 2;
var MODIFIED   = 3;
var REPLACED   = 4;
var INSERTED   = 5;
var WHITESPACE = 6;
var CONFLICT   = 7;

var line_classes = [null, "context", "deleted", "modified", "replaced", "inserted", "modified whitespace", "conflict"];

function recompact(id)
{
  var table = fileById(id), count = 0;

  table.each(function (index, table)
    {
      if (!table.disableCompact)
        for (index = 0; index < table.tBodies.length; ++index)
        {
          var tbody = table.tBodies.item(index);
          if (tbody.firstChild.nodeType == Node.COMMENT_NODE)
          {
            var comment = tbody.firstChild;
            while (comment.nextSibling)
            {
              tbody.removeChild(comment.nextSibling);
              ++count;
            }
          }
        }
    });
}

function decompact(id)
{
  var table = fileById(id);

  if (!table.children("colgroup").size())
    table.prepend("<colgroup><col class=edge><col class=linenr><col class=line><col class=middle><col class=middle><col class=line><col class=linenr><col class=edge></colgroup>");

  table.each(function (index, table)
    {
      var parent;

      if (table.hasAttribute("critic-parent-index"))
        parent = "p" + table.getAttribute("critic-parent-index");
      else
        parent = "";

      if (table.disableCompact)
        return;

      function unpack(line)
      {
        return line.replace(/<([bi])([a-z]+)>/g, "<$1 class=$2>");
      }

      for (index = 0; index < table.tBodies.length; ++index)
      {
        var tbody = table.tBodies.item(index);
        if (tbody.firstChild.nodeType == Node.COMMENT_NODE)
        {
          var data = JSON.parse(tbody.firstChild.nodeValue);

          var file_id = data[0];
          var sides = data[1];
          var old_offset = data[2];
          var new_offset = data[3];
          var lines = data[4];
          var html = "";

          for (var line_index = 0; line_index < lines.length; ++line_index)
          {
            var line = lines[line_index];

            var line_type = line[0];
            var item_index = 1;

            var line_old_offset = 0, line_new_offset = 0;

            if (line_type != INSERTED)
              line_old_offset = old_offset++;
            if (line_type != DELETED && line_type != CONFLICT)
              line_new_offset = new_offset++;

            var line_id = parent + "f" + file_id + "o" + line_old_offset + "n" + line_new_offset;

            html += "<tr class='line " + line_classes[line_type] + "' id='" + line_id + "'>" +
                    "<td class=edge>&nbsp;</td>" +
                    "<td class='linenr old'>";

            if (sides == 2)
            {
              if (line_type != INSERTED)
                html += line_old_offset + "</td><td class='line old' id=" + parent + "f" +
                        file_id + "o" + line_old_offset + ">" + unpack(line[item_index++]);
              else
                html += "&nbsp;<td class='line old'>&nbsp;";

              html += "</td><td class='middle' colspan=2>&nbsp;</td>" +
                      "<td class='line new'";

              if (line_type != DELETED && line_type != CONFLICT)
                html += " id=" + parent + "f" + file_id + "n" + line_new_offset + ">" +
                        unpack(line[item_index++]) + "</td><td class='linenr new'>" + line_new_offset;
              else
                html += ">&nbsp;</td><td class='linenr old'>&nbsp;";
            }
            else
            {
              if (line_type == DELETED)
                html += line_old_offset + "</td><td class='line single old' id=" + parent + "f" +
                        file_id + "o" + line_old_offset + " colspan=4>" + unpack(line[item_index++]) +
                        "</td><td class='linenr new'>" + line_old_offset;
              else
                html += line_new_offset + "</td><td class='line single new' id=" + parent + "f" +
                        file_id + "n" + line_new_offset + " colspan=4>" + unpack(line[item_index++]) +
                        "</td><td class='linenr new'>" + line_new_offset;
            }

            html += "</td><td class=edge>&nbsp;</td></tr>";
          }

          tbody = $(tbody);
          tbody.append(html);

          if (typeof review != "undefined")
          {
            tbody.find("td.line").mousedown(startCommentMarking);
            tbody.find("td.line").mouseover(continueCommentMarking);
            tbody.find("td.line").mouseup(endCommentMarking);
          }

          updateBlame(parseInt(id));
        }
      }
    });
}

function extractFile(id)
{
  var table = fileById(id);

  if (table.size())
  {
    var placeholder = $("<div style='display: none'>");

    extractedFiles[id] = [table, placeholder];

    table.replaceWith(placeholder);
  }
}

function restoreFile(id)
{
  if (id in extractedFiles)
  {
    var table = extractedFiles[id][0];
    var placeholder = extractedFiles[id][1];

    delete extractedFiles[id];

    placeholder.replaceWith(table);

    if (typeof review != "undefined")
    {
      table.find("td.line").mousedown(startCommentMarking);
      table.find("td.line").mouseover(continueCommentMarking);
      table.find("td.line").mouseup(endCommentMarking);
    }
  }
}

function restoreAllFiles()
{
  for (var id in extractedFiles)
    restoreFile(id);
}

function toggleFile(table)
{
  table = $(table);

  if (table.hasClass("expanded"))
    collapseFile(table.attr("critic-file-id"));
  else
    expandFile(table.attr("critic-file-id"));

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();
}

function fileById(id)
{
  if (typeof parentsCount != "undefined")
  {
    var selector = [];
    for (index = 0; index < parentsCount; ++index)
      selector.push("#p" + index + "f" + id);
    return $(selector.join(", "));
  }
  else
    return $("#f" + id);
}

function collapseFile(id)
{
  var table = fileById(id);

  table.removeClass("expanded");
  recompact(id);

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();

  delete expandedFiles[id];
  saveState();
}

function expandFile(id, scroll)
{
  if (typeof parentsCount != "undefined")
    if (selectedParent == null || !document.getElementById("p" + selectedParent + "f" + id))
      for (var index = 0; index < parentsCount; ++index)
        if (document.getElementById("p" + index + "f" + id))
        {
          selectParent(index);
          break;
        }

  restoreFile(id);

  var table = currentFile = fileById(id);

  decompact(id);
  table.addClass("show expanded");

  if (scroll)
  {
    if (table.offset().top + table.height() > scrollY + innerHeight || table.offset().top < scrollY)
      scrollTo(scrollX, table.offset().top);
  }

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();

  if (!expandedFiles[id])
  {
    expandedFiles[id] = true;
    saveState();
  }
}

function showFile(id)
{
  if (typeof parentsCount != "undefined")
    if (selectedParent == null || !document.getElementById("p" + selectedParent + "f" + id))
      for (var index = 0; index < parentsCount; ++index)
        if (document.getElementById("p" + index + "f" + id))
        {
          selectParent(index);
          break;
        }

  restoreFile(id);

  var table = fileById(id);

  table.addClass("show expanded");
}

function collapseAll(implicit)
{
  var changed = false;

  $("table.file.expanded").each(function (index, table)
    {
      changed = true;

      table = $(table);
      table.removeClass("expanded");

      var id = table.attr("critic-file-id");

      recompact(id);

      if (table.hasClass("show"))
        expandedFiles[id] = false;
      else
        delete expandedFiles[id];
    });

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();

  expandedFiles = {};

  if (!implicit && changed)
    saveState();
}

function expandAll()
{
  showAll(true);

  var changed = false;

  $("table.file").each(function (index, table)
    {
      table = $(table);

      var id = table.attr("critic-file-id");

      if (!table.hasClass("expanded"))
      {
        decompact(id);
        changed = true;
        table.addClass("expanded");
      }

      expandedFiles[id] = true;
    });

  if (changed)
    saveState();

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();
}

var mode = "hide";

function hideAll(implicit)
{
  if (/showcomments?$/.test(location.pathname))
    return;

  mode = "hide";
  $("table.file").each(function (index, table)
    {
      table = $(table);

      table.removeClass("show");

      recompact(table.attr("critic-file-id"));
    });

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();

  expandedFiles = {};

  if (!implicit)
    saveState();
}

function showAll(implicit)
{
  mode = "show";

  restoreAllFiles();

  var changed = false;

  $("table.file").each(function (index, table)
    {
      table = $(table);

      var id = table.attr("critic-file-id");

      if (!table.hasClass("show"))
      {
        changed = true;
        if (table.hasClass("expanded"))
          decompact(id);
        table.addClass("show");
      }

      if (!(id in expandedFiles))
        expandedFiles[id] = false;
    });

  if (!implicit && changed)
    saveState();

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();
}

var isRestoringState = false;

function saveState(replace)
{
  if (!isRestoringState)
  {
    var state = { expandedFiles: expandedFiles, scrollLeft: scrollX, scrollTop: scrollY };

    if (!replace)
    {
      if (typeof history.pushState == "function")
      {
        history.pushState(state, document.title);

        var base = document.getElementsByTagName("base")[0];
        if (base)
        {
          var base_href = base.href;
          base.href = "";
          base.href = base_href;
        }
      }
    }
    else
    {
      if (typeof history.replaceState == "function")
      {
        history.replaceState(state, document.title);

        var base = document.getElementsByTagName("base")[0];
        if (base)
        {
          var base_href = base.href;
          base.href = "";
          base.href = base_href;
        }
      }
    }
  }
}

function restoreState(state)
{
  isRestoringState = true;

  hideAll(true);

  if (state)
  {
    for (var id in state.expandedFiles)
      if (state.expandedFiles[id])
        expandFile(id);
      else
      {
        collapseFile(id);
        showFile(id);
      }

    if (typeof state.scrollTop == "number")
      window.scrollTo(state.scrollLeft, state.scrollTop);
  }

  isRestoringState = false;
}

var selectedParent = null;

function selectParent(index)
{
  for (var other = 0; other < parentsCount; ++other)
    if (other != index)
      $(".parent" + other).removeClass("show");

  $(".parent").removeClass("show");
  $("#p" + index).addClass("show");

  $(".parent" + index).addClass("show");

  selectedParent = index;

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();
}

document.addEventListener("click", function (ev)
  {
    var node = ev.target;
    while (node)
    {
      if (node.nodeName.toLowerCase() == "thead" || node.nodeName.toLowerCase() == "tfoot" || hasClass(node, "file-summary"))
      {
        toggleFile($(node).parents("table"));
      }
      else if (node.nodeName.toLowerCase() == "a")
        return;

      node = node.parentNode;
    }
  }, false);

var currentFile = null;

keyboardShortcutHandlers.push(function (key)
  {
    switch (key)
    {
    case 32:
      if (!currentFile)
        if (mode == "hide")
          hideAll();
        else
          collapseAll();

      if (scrollY + innerHeight >= (currentFile ? (currentFile.offset().top + currentFile.height()) : document.documentElement.scrollHeight))
      {
        var nextFile = currentFile ? currentFile.nextAll("table.file").first() : $("table.file.first");

        if (currentFile && currentFile.length)
        {
          var id = currentFile.first().attr("critic-file-id");

          if (mode == "hide")
          {
            $(currentFile).removeClass("show");

            if (typeof CommentMarkers != "undefined")
              CommentMarkers.updateAll();
          }
          else
            collapseFile(id);

          if (typeof markFile != "undefined")
          {
            var parent_index = currentFile.first().attr("critic-parent-index");
            if (parent_index)
              parent_index = parseInt(parent_index);
            else
              parent_index = null;
            markFile("reviewed", parseInt(currentFile.first().attr("critic-file-id")), parent_index);
          }
        }

        if (nextFile.length)
        {
          expandFile(nextFile.first().attr("critic-file-id"), true);
          return true;
        }
        else
          currentFile = null;
      }
      return false;

    case "e".charCodeAt(0):
      expandAll();
      return true;

    case "c".charCodeAt(0):
      collapseAll();
      return true;

    case "s".charCodeAt(0):
      showAll();
      return true;

    case "h".charCodeAt(0):
      hideAll();
      return true;

    case "m".charCodeAt(0):
      detectMoves();
      return true;

    case "b".charCodeAt(0):
      blame();
      return true;

    default:
      if (typeof parentsCount != "undefined")
        if (key >= "1".charCodeAt(0) && key <= "0".charCodeAt(0) + parentsCount)
        {
          selectParent(key - "1".charCodeAt(0));
          return true;
        }
    }
  });

$(document).ready(function ()
  {
    if (typeof keyboardShortcuts == "undefined" || keyboardShortcuts)
      document.addEventListener("keypress", function (ev)
        {
          if (ev.ctrlKey || ev.shiftKey || ev.altKey || ev.metaKey)
            return;

          if (/^(?:input|textarea)$/i.test(ev.target.nodeName))
            if (ev.keyCode == 32 || /textarea/i.test(ev.target.nodeName) || !/^(?:checkbox|radio)$/i.test(ev.target.type))
              return;

          /* Handling non-printable keys. */
          if (ev.keyCode == 32)
          {
            if (handleKeyboardShortcut(ev.keyCode))
              ev.preventDefault();
          }
          else if (!ev.which)
            return;
          /* Handling printable keys */
          else if (handleKeyboardShortcut(ev.keyCode))
            ev.preventDefault();
        }, false);
  });

function setSpacerContext(spacer, context)
{
  var target = $(spacer).nextAll("tr.context").find("td");
  if (!target.size())
  {
    var row = $("<tr class=context><td class=context colspan=8></td></tr>");
    $(spacer).after(row);
    target = row.find("td");
  }
  target.text(context);
}

function expand(select, file_id, sha1, where, oldOffset, newOffset, total)
{
  if (select.value == "none")
    return;

  var spacerCell = select.parentNode;
  var spacerRow = spacerCell.parentNode;
  var table = spacerRow.parentNode.parentNode;
  var count = parseInt(select.value);
  var deltaOffset = 0, deltaTotal = count, deltaFactor;

  table.disableCompact = true;

  if (where != 'top')
    deltaOffset = count;
  if (where == 'middle')
    deltaFactor = 2;
  else
    deltaFactor = 1;
  deltaTotal *= deltaFactor;

  if (count == total)
    spacerCell.innerHTML = "&nbsp;";
  else
  {
    select.selectedIndex = 0;

    var newTotal = total - deltaTotal;

    select.onchange = function () { expand(this, file_id, sha1, where, oldOffset + deltaOffset, newOffset + deltaOffset, total - deltaTotal); };
    select.options[0].textContent = (total - deltaTotal) + ' lines not shown';
    select.lastChild.value = newTotal;

    if (select.options.length == 5 && newTotal < 50 * deltaFactor)
      select.options[3] = null;
    if (select.options.length == 4 && newTotal < 25 * deltaFactor)
      select.options[2] = null;
    if (select.options.length == 3 && newTotal < 10 * deltaFactor)
      select.options[1] = null;

    select.blur();
  }

  var ranges = [];

  /* Request lines above the spacer. */
  if (where != "top")
    ranges.push({ offset: newOffset, count: count, context: false });

  /* Request lines below the spacer. */
  if (where != "bottom" && (where == 'top' || count < total))
    ranges.push({ offset: newOffset + total - count, count: count, context: true });

  var data = { repository_id: repository.id,
               path: files[file_id].path,
               sha1: sha1,
               ranges: ranges,
               tabify: typeof tabified != "undefined" };

  var operation = new Operation({ action: "fetch lines",
                                  url: "fetchlines",
                                  data: data });
  var result = operation.execute();

  /* Add lines below the spacer. */
  if (where != 'bottom' && (where == 'top' || count < total))
  {
    var range = result.ranges.pop();
    var lines = range.lines;
    var tbody = nextTableSection(spacerRow);
    var anchor = tbody.firstChild;

    for (var index = 0; index < lines.length; ++index)
      tbody.insertBefore(makeLine(file_id,
                                  oldOffset + total - count + index,
                                  lines[index],
                                  lines[index],
                                  newOffset + total - count + index),
                         anchor);

    setSpacerContext(spacerRow, range.context || "");

    if (typeof CommentMarkers != "undefined")
      CommentMarkers.updateAll();
  }

  if (where != "top")
  {
    var lines = result.ranges.pop().lines;
    var tbody = previousTableSection(spacerRow);

    for (var index = 0; index < lines.length; ++index)
      tbody.appendChild(makeLine(file_id,
                                 oldOffset + index,
                                 lines[index],
                                 lines[index],
                                 newOffset + index));

    if (count == total && where == 'middle')
    {
      var next = nextTableSection(spacerRow);
      var spacerSection = spacerRow.parentNode;

      spacerSection.parentNode.removeChild(spacerSection);
      while (next.firstChild)
        tbody.appendChild(next.firstChild);
      next.parentNode.removeChild(next);
    }
  }

  if (typeof CommentMarkers != "undefined")
    CommentMarkers.updateAll();
}

function createReview()
{
  location.href = "createreview?repository=" + repository.id + "&commits=" + changeset.commits.join(",");
}

function customProcessCommits()
{
  location.href = "processcommits?review=" + review.id + "&commits=" + changeset.commits.join(",");
}

function fetchFile(file_id, side, replace_tbody)
{
  var data = { repository_id: repository.id,
               path: files[file_id].path,
               sha1: files[file_id][side + "_sha1"],
               ranges: [{ offset: 1, count: -1, context: false }],
               tabify: typeof tabified != "undefined" };

  var operation = new Operation({ action: "fetch lines",
                                  url: "fetchlines",
                                  data: data });
  var result = operation.execute();

  var lines = result.ranges[0].lines;
  var html = "<tbody class=lines>";
  var deleted = side == "old";
  var row_class = deleted ? "deleted" : "inserted";

  for (var offset = 1; offset <= lines.length; ++offset)
  {
    var line = lines[offset - 1] || "&nbsp;";
    var row_id = "f" + file_id + (deleted ? "o" + offset + "n0" : "o0n" + offset);

    html += "<tr class='line " + row_class + "' id=" + row_id + ">"
          +   "<td class=edge></td>"
          +   "<td class='linenr old'>" + offset + "</td>"
          +   "<td class='line single " + side + "' colspan=4>" + line + "</td>"
          +   "<td class='linenr new'>" + offset + "</td>"
          +   "<td class=edge></td>"
          + "</tr>";
  }

  html += "</tbody>";

  var tbody = $(html);

  if (typeof review != "undefined")
  {
    tbody.find("td.line").mousedown(startCommentMarking);
    tbody.find("td.line").mouseover(continueCommentMarking);
    tbody.find("td.line").mouseup(endCommentMarking);
  }

  tbody.replaceAll($(replace_tbody));
}

function detectMoves()
{
  var content = $("<div title='Detect Moved Code' class='detectmoves'><p>Source file:<br><select class='source'><option value='any'>Any</option></select></p><p>Target file:<br><select class='target'><option value='any'>Any</option></select></p></div>");

  var source = content.find("select.source");
  var target = content.find("select.target");
  var fileids = {};
  var paths = [];

  for (var name in files)
    if (/^\d+$/.test(name))
    {
      var path = files[name].path;

      fileids[path] = name;
      paths.push(path);
    }

  paths.sort();

  for (var index = 0; index < paths.length; ++index)
  {
    var path = paths[index];
    var fileid = fileids[path];

    source.append("<option value='" + fileid + "'>" + htmlify(path) + "</option>");
    target.append("<option value='" + fileid + "'>" + htmlify(path) + "</option>");
  }

  function finish()
  {
    var source_arg = source.val() == "any" ? "" : "&sourcefiles=" + source.val();
    var target_arg = target.val() == "any" ? "" : "&targetfiles=" + target.val();

    if (typeof review != "undefined")
      location.href = "/" + changeset.parent.sha1 + ".." + changeset.child.sha1 + "?review=" + review.id + "&moves=yes" + source_arg + target_arg;
    else
      location.href = "/" + repository.name + "/" + changeset.parent.sha1 + ".." + changeset.child.sha1 + "?moves=yes" + source_arg + target_arg;
  }

  content.dialog({ width: 600,
                   buttons: { Search: function () { finish(); content.dialog("close"); },
                              Cancel: function () { content.dialog("close"); } } });
}

var BLAME = null;

function fetchBlame()
{
  if (BLAME === null)
  {
    var files = [];

    for (var file_id in blocks)
    {
      var raw_blocks = blocks[file_id];
      var fine_blocks = new Array(raw_blocks.length);

      for (var index = 0; index < raw_blocks.length; ++index)
        fine_blocks[index] = { first: raw_blocks[index][0], last: raw_blocks[index][1] };

      files.push({ id: ~~file_id, blocks: fine_blocks });
    }

    var operation = new Operation({ action: "blame lines",
                                    url: "blame",
                                    data: { repository_id: repository.id,
                                            changeset_id: changeset.id,
                                            files: files }
                                  });
    var result = operation.execute();

    if (result)
    {
      BLAME = result;
      BLAME.color_index = 0;

      for (var index = 0; index < BLAME.commits.length; ++index)
      {
        var commit = BLAME.commits[index];

        if (commit.original)
          BLAME.original = commit;
        if (commit.current)
          BLAME.current = commit;
      }
    }
  }
}

function updateBlame(file_id)
{
  function getColor(index)
  {
    var compentvalues = [0xff, 0x80, 0xc0, 0x40, 0xe0, 0xa0, 0x60, 0x20];
    var cv1 = compentvalues[parseInt(index / 6) % 8], cv2 = parseInt(cv1 / 2), pattern;

    cv1 = cv1.toString(16);
    if (cv1.length == 1)
      cv1 = "0" + cv1;

    cv2 = cv2.toString(16);
    if (cv2.length == 1)
      cv2 = "0" + cv2;

    switch (index % 6)
    {
    case 0: pattern = "hhllll"; break;
    case 1: pattern = "llhhll"; break;
    case 2: pattern = "llllhh"; break;
    case 3: pattern = "hhhhll"; break;
    case 4: pattern = "hhllhh"; break;
    case 5: pattern = "llhhhh"; break;
    }

    var color = pattern.replace(/hh/g, cv1).replace(/ll/g, cv2);

    console.log(color);

    return color;
  }

  if (BLAME)
  {
    for (var file_index = 0; file_index < BLAME.files.length; ++file_index)
    {
      var file = BLAME.files[file_index];

      if (!file_id || file.id === file_id)
      {
        for (var block_index = 0; block_index < file.blocks.length; ++block_index)
        {
          var lines = file.blocks[block_index].lines;

          for (var line_index = 0; line_index < lines.length; ++line_index)
          {
            var line = lines[line_index];
            var commit = BLAME.commits[line.commit];
            var row = $("#f" + file.id + "n" + line.offset).parent(), color_selector, tooltip_selector;

            function addTooltip(element, commit)
            {
              element.tooltip({
                track: true,
                fade: 250,
                bodyHandler: function ()
                  {
                    return $("<div class='blame-tooltip'><b><u>" + htmlify(commit.author_name) + " &lt;" + htmlify(commit.author_email) + "></u></b>" +
                             "<pre>" + htmlify(commit.message) + "</pre></div>");
                  },
                showURL: false,
                extraClass: "blame-tooltip"
              });
            }

            if (commit.original)
              addTooltip(row.children("td.line"), commit);
            else
            {
              if (!commit.color)
                commit.color = getColor(BLAME.color_index++);

              if (row.children("td.line.single").size())
                row.children("td.linenr").css("background-color", "#" + commit.color);
              else
                row.children("td.middle, td.linenr.new").css("background-color", "#" + commit.color);

              if (!row.hasClass("inserted"))
                addTooltip(row.children("td.line.old"), BLAME.original);

              addTooltip(row.children("td.line.new"), commit);
            }
          }
        }
      }
    }
  }
}

function blame()
{
  fetchBlame();
  updateBlame();
}

$(document).ready(function ()
  {
    $("table.commit-files td.path").click(function (ev)
      {
        try
        {
          if (mode == "hide")
            hideAll(true);
          else
            collapseAll(true);

          file_id = ev.currentTarget.parentNode.getAttribute("critic-file-id");

          expandFile(file_id, true);
        }
        catch (e)
        {
          console.log(e.message + "\n" + e.stacktrace);
        }

        ev.preventDefault();
      });

    var match = /#f(\d+)([on])(\d+)/.exec(location.hash);
    if (match)
    {
      expandFile(parseInt(match[1]));
      location.hash = location.hash;
    }

    $("table.commit-files td.parent").mouseover(function (ev)
      {
        var target = $(ev.currentTarget);

        target.addClass("hover");

        if (target.prev("td.parent").first().attr("critic-parent-index") == target.attr("critic-parent-index"))
          target.prev("td.parent").first().addClass("hover");
        if (target.next("td.parent").first().attr("critic-parent-index") == target.attr("critic-parent-index"))
          target.next("td.parent").first().addClass("hover");
      });

    $("table.commit-files td.parent").mouseout(function (ev)
      {
        var target = $(ev.currentTarget);

        target.removeClass("hover");

        if (target.prev("td.parent").first().attr("critic-parent-index") == target.attr("critic-parent-index"))
          target.prev("td.parent").first().removeClass("hover");
        if (target.next("td.parent").first().attr("critic-parent-index") == target.attr("critic-parent-index"))
          target.next("td.parent").first().removeClass("hover");
      });

    $("table.commit-files td.parent").click(function (ev)
      {
        var target = $(ev.currentTarget);
        var file_id = target.parentsUntil("table").filter("tr").attr("critic-file-id");
        var parent = target.attr("critic-parent-index");

        if (mode == "hide")
          hideAll(true);
        else
          collapseAll(true);

        selectParent(parent);
        expandFile(file_id, true);

        ev.preventDefault();
      });
  });

function applyLengthLimit(lines)
{
  lines.each(
    function (index, element)
    {
      var limit = element.getAttribute("critic-length-limit");
      if (limit)
      {
        var match = /(\d+)-(\d+)/.exec(limit);
        var low_limit = parseInt(match[1]);
        var high_limit = parseInt(match[2]);

        if (element.textContent.length > low_limit)
        {
          var iterator = document.createNodeIterator(element, NodeFilter.SHOW_TEXT, null, false);
          var texts = [], text, seen = 0;

          while (text = iterator.nextNode())
            texts.push(text);

          for (var index = 0; index < texts.length; ++index)
          {
            var text = texts[index];
            var html = "";
            var offset = Math.min(Math.max(0, low_limit - seen), text.length), end = Math.min(text.length, Math.max(0, high_limit - seen));

            if (offset > 0)
            {
              html += htmlify(text.data.substring(0, offset));
              seen += offset;
            }

            for (; offset < end; ++offset)
            {
              var redness = Math.min(100, 100 * (seen - low_limit) / (high_limit - low_limit)).toFixed(1);
              html += "<span style='color: rgb(" + redness + "%, 0%, 0%)'>" + htmlify(text.data.substring(offset, offset + 1)) + "</span>";
              ++seen;
            }

            if (offset < text.length)
              html += "<span style='color: rgb(100%, 0%, 0%)'>" + htmlify(text.data.substring(offset)) + "</span>"

            $("<div>" + html + "</div>").contents().replaceAll($(text));
          }
        }
      }
    });
}

(function() {
  /*Handle resizing of the left and right diff views
    by dragging divider between them. */

  var currentCols = null; ///< cached reference to the col elements that are being resized
  var tableCoord = { left: 0, width: 0 }
  const HALF_DIVIDER_WIDTH = 15; ///< half of the width of the divider between diff views (somewhat arbitrary)

  document.addEventListener('mousedown', handleMouseDown);
  document.addEventListener('dblclick', handleDblClick);

  function handleMouseDown(e)
  {
    if (e.button != 0)
      return;

    var el = e.target;
    if (el.tagName.toLowerCase() == 'td' && el.className == 'middle')
      if (currentCols = findTableCols(el))
      {
        /* Calculate offsets from the sibling cells of the clicked one.
           WebKit is unable to get dimensions from the col elements. */
        var panes = el.parentNode.querySelectorAll("td.line");
        tableCoord.left = $(panes[0]).offset().left;
        tableCoord.width = $(panes[0]).width() + $(panes[1]).width();

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
        e.preventDefault();
      }
  }

  function handleMouseUp(e)
  {
    currentCols = null;
    document.removeEventListener('mouseup', handleMouseUp);
    document.removeEventListener('mousemove', handleMouseMove);
  }

  function handleMouseMove(e)
  {
    if (currentCols)
    {
      var leftDiffPaneWidth = e.pageX - tableCoord.left - HALF_DIVIDER_WIDTH;
      leftDiffPaneWidth = Math.min(tableCoord.width, Math.max(0, leftDiffPaneWidth));
      currentCols[0].style.width = leftDiffPaneWidth + 'px';
      currentCols[1].style.width = (tableCoord.width - leftDiffPaneWidth) + 'px';
      if (typeof CommentMarkers != "undefined")
        CommentMarkers.updateAll();
    }
  }

  /* Center diff division (reset to default). */
  function handleDblClick(e)
  {
    if (e.target.className != 'middle')
      return;

    var cols = findTableCols(e.target);
    if (cols)
    {
      cols[0].removeAttribute('style');
      cols[1].removeAttribute('style');
      if (typeof CommentMarkers != "undefined")
        CommentMarkers.updateAll();
    }
  }

  /* Iterate upwards from the tableChild element looking for
     a parent table and its two col.line elements. */
  function findTableCols(tableChild)
  {
    var table = tableChild;
    while (table = table.parentNode)
      if (table.tagName.toLowerCase() == 'table')
        break;

    if (table)
    {
      var cols = table.querySelectorAll('colgroup col.line');
      if (cols.length == 2)
        return cols;
    }

    return null;
  }
})();

window.addEventListener("popstate", function (ev)
  {
    restoreState(ev.state);
  }, false);

if (typeof history.replaceState == "function")
  window.addEventListener("scroll", function (ev)
    {
      saveState(true);
    }, false);
