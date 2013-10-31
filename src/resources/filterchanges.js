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

function checkDirectory(line)
{
  var level = parseInt(line.getAttribute("critic-level"));
  var all_checked = true;
  var dirline = line;

  $(line).nextAll("tr").each(function (index, line)
    {
      if (parseInt(line.getAttribute("critic-level")) <= level)
        return false;

      if (line.className == "file")
        $(line).find("input").each(function () { if (!this.checked) all_checked = false; });

      return all_checked;
    });

  $(line).find("input").each(function () { this.checked = all_checked; });
}

function checkDirectories()
{
  $("tr.directory").each(function (index, line)
    {
      checkDirectory(line);
    });
}

$(document).ready(function ()
  {
    $("tr.directory").click(function (ev)
      {
        var line = $(ev.currentTarget);
        var level = parseInt(line.attr("critic-level"));
        var checkbox = line.find("input");

        var on;
        if (ev.target.nodeName.toLowerCase() != "input")
        {
          checkbox.each(function () { on = this.checked = !this.checked; });
          ev.preventDefault();
        }
        else
          checkbox.each(function () { on = this.checked; });

        line.nextAll("tr").each(function (index, line)
          {
            if (parseInt(line.getAttribute("critic-level")) <= level)
              return false;

            $(line).find("input").each(function () { this.checked = on; });
          });

        line.prevAll("tr.directory").each(function (index, line)
          {
            var line_level = parseInt(this.getAttribute("critic-level"));
            if (line_level < level)
            {
              if (!ev.currentTarget.checked)
                $(line).find("input").each(function () { this.checked = false; });
              else
                checkDirectory(line);

              level = line_level;
            }
          });
      });

    $("tr.file").click(function (ev)
      {
        var line = $(ev.currentTarget);
        var level = parseInt(line.attr("critic-level"));

        if (ev.target.nodeName.toLowerCase() != "input")
        {
          $(ev.currentTarget).find("input").each(function () { this.checked = !this.checked; });
          ev.preventDefault();
        }

        line.prevAll("tr.directory").each(function (index, line)
          {
            var line_level = parseInt(this.getAttribute("critic-level"));
            if (line_level < level)
            {
              if (!ev.currentTarget.checked)
                $(line).find("input").each(function () { this.checked = false; });
              else
                checkDirectory(line);

              level = line_level;
            }
          });
      });

    $("button.display").click(function ()
      {
        var files = [];

        $("tr.file").each(function (index, line)
          {
            var selected;

            $(line).find("input").each(function () { selected = this.checked; });

            if (selected)
              files.push(line.getAttribute("critic-file-id"));
          });

        if (files.length != 0)
          if (commitRange)
            location.href = "/showcommit?review=" + review.id + "&first=" + commitRange.first + "&last=" + commitRange.last + "&filter=files&file=" + files.join(",");
          else
            location.href = "/showcommit?review=" + review.id + "&filter=files&file=" + files.join(",");
        else
          alert("No files selected!");
      });
  });

keyboardShortcutHandlers.push(function (key)
  {
    if (key == "g".charCodeAt(0))
    {
      $("button.display").click();
      return true;
    }
    else if (key == "a".charCodeAt(0))
    {
      $("tr.directory[critic-level=-1]").click();
      return true;
    }
  });
