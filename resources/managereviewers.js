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

var currentReviewer = null;

function selectReviewer(reset)
{
  var reviewer = $("input.reviewer").val();

  if (reviewer == currentReviewer)
    return;

  if (reviewer == "")
    if (reset)
      $("input.reviewer").val(reviewer = currentReviewer);
    else
      return;

  function handleNoSuchUser(result)
  {
    $("tr.reviewer span.message").text("No such user.");
    return true;
  }

  $("tr.reviewer span.message").text("");

  var operation = new Operation({ action: "fetch assigned changes",
				  url: "getassignedchanges",
				  data: { review_id: review.id,
					  user_name: reviewer },
				  failure: { nosuchuser: handleNoSuchUser }});
  var result = operation.execute();

  if (result)
  {
    var files = {};

    for (var index = 0; index < result.files.length; ++index)
      files[result.files[index]] = true;

    currentReviewer = reviewer;

    $("tr.file").each(
      function ()
      {
	$(this).find("input").get(0).checked = $(this).attr("critic-file-id") in files;
      });

    checkDirectories();

    $("input.reviewer").autocomplete("close");
  }
}

function checkDirectory(line)
{
  line = $(line);

  var level = parseInt(line.attr("critic-level"));
  var all_checked = true;
  var dirline = line;

  line.nextAll("tr").each(function (index, line)
    {
      if (parseInt(line.getAttribute("critic-level")) <= level)
        return false;

      if (line.className == "file")
        $(line).find("input").each(function () { if (!this.checked) all_checked = false; });

      return all_checked;
    });

  line.find("input").each(function () { this.checked = all_checked; });
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
        var checkbox = line.find("input").get(0);

        var on;
        if (ev.target.nodeName.toLowerCase() != "input")
        {
          on = checkbox.checked = !checkbox.checked;
          ev.preventDefault();
        }
        else
          on = checkbox.checked;

        line.nextAll("tr").each(
          function (index, line)
          {
            if (parseInt(line.getAttribute("critic-level")) <= level)
              return false;

            $(line).find("input").each(function () { this.checked = on; });
          });

        line.prevAll("tr.directory").each(
          function (index, line)
          {
            var line_level = parseInt(line.getAttribute("critic-level"));
            if (line_level < level)
            {
              if (!checkbox.checked)
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
        var checkbox = line.find("input").get(0);

        var on;
        if (ev.target.nodeName.toLowerCase() != "input")
        {
          on = checkbox.checked = !checkbox.checked;
          ev.preventDefault();
        }
        else
          on = checkbox.checked;

        line.prevAll("tr.directory").each(
          function (index, line)
          {
            var line_level = parseInt(this.getAttribute("critic-level"));
            if (line_level < level)
            {
              if (!checkbox.checked)
                $(line).find("input").each(function () { this.checked = false; });
              else
                checkDirectory(line);

              level = line_level;
            }
          });
      });

    $("input.reviewer").autocomplete({ source: users });
    $("input.reviewer").keypress(function (ev)
      {
        if (ev.keyCode == 13)
          selectReviewer(false);
      });
    $("input.reviewer").blur(function (ev)
      {
	setTimeout(function () { selectReviewer(true); }, 100);
      });

    $("button.save").click(function ()
      {
        var files = [], reviewer = $("input.reviewer").val();

        $("tr.file").each(function ()
          {
	    var row = $(this);
            if (row.find("input").get(0).checked)
              files.push(parseInt(row.attr("critic-file-id")));
          });

	var operation = new Operation({ action: "assign changes",
					url: "setassignedchanges",
					data: { review_id: review.id,
						user_name: reviewer,
						files: files }});

	if (operation.execute())
          $("tr.reviewer span.message").text("Assignments saved.");
      });

    $("input.reviewer").val(user.name);

    selectReviewer();

    $("span.reviewer").click(function (ev)
      {
        $("input.reviewer").val($(this).attr("critic-username"));
        selectReviewer();
      });
  });
