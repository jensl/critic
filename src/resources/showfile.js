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

/* -*- mode: text; indent-tabs-mode: nil -*- */

function highlightLines(markers)
{
  var start = /f\d+n(\d+)/.exec(markers.firstLine.id)[1];
  var end = /f\d+n(\d+)/.exec(markers.lastLine.id)[1];
  var href = location.href;

  var match = /^(.*)&line=\d+(?:-\d+)?(.*)$/.exec(href);

  if (match)
    href = match[1] + match[2];

  if (start == end)
    location.href = href + "&line=" + start;
  else
    location.href = href + "&line=" + start + "-" + end;

  markers.remove();
  currentMarkers = null;
}

var defaultHandleMarkedLines = handleMarkedLines;

handleMarkedLines = function (markers)
  {
    if (typeof review == "undefined")
      highlightLines(markers);
    else
    {
      CommentChain.extraButtons = { "Link to Lines": function () { highlightLines(currentMarkers); return true; } };
      defaultHandleMarkedLines(markers);
    }
  };

$(document).ready(function ()
  {
    $("td.line").mousedown(startCommentMarking);
    $("td.line").mouseover(continueCommentMarking);
    $("td.line").mouseup(endCommentMarking);

    if (typeof firstSelectedLine == "number")
    {
      var markers = new CommentMarkers;
      markers.setLines($("td.first-selected"), $("td.last-selected"));
      markers.setType("issue", "open");
    }
  });
