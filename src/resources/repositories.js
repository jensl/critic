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

/* -*- mode: js; indent-tabs-mode: nil -*- */

$(function ()
  {
    $("a.button").button();

    $("tr.repository").click(
      function (ev)
      {
        $(ev.currentTarget).next("tr.details").toggleClass("show");
        ev.preventDefault();
      });

    if (location.hash)
      $("tr.details." + location.hash.substring(location.hash.indexOf("#") + 1)).addClass("show");

    $("tr.branch").click(
      function (ev)
      {
        var branch_row = $(ev.currentTarget);

        var branch_id = parseInt(branch_row.attr("critic-branch-id"));
        var user_ids = branch_row.attr("critic-user-ids").split(",").map(Number);

        var operation = new Operation({ action: "fetch log",
                                        url: "trackedbranchlog",
                                        data: { branch_id: branch_id } });
        var result = operation.execute();

        var html = "<div class='trackedbranchlog' title='Update Log'>";

        if (result.items.length)
        {
          html += "<div class='log'><table><tr><th colspan=2>Update log:</th></tr>";

          for (var index = 0; index < result.items.length; ++index)
          {
            var item = result.items[index];

            html += "<tr><td class='when'>" + new Date(item.time * 1000) + "</td>" +
                        "<td class='range'>" +
                          "<a href='" + result.repository.name + "/" + item.from_sha1 + ".." + item.to_sha1 + "'>" +
                            item.from_sha1.substring(0, 8) + ".." + item.to_sha1.substring(0, 8) +
                          "</a>" +
                        "</td></tr>";

            if (item.hook_output.trim())
              html += "<tr><td class='output' colspan=2><pre>" + htmlify(item.hook_output) + "</pre></td></tr>";
          }

          html += "</table></div>";
        }

        html += "<p>";
        html += "<b>Last check:</b> " + (result.previous === null ? "Never" : new Date(result.previous * 1000)) + "<br>";
        html += "<b>Next scheduled check:</b> " + (result.next === null ? "ASAP" : new Date(result.next * 1000));
        html += "</p>";

        html += "</div>";

        var dialog = $(html);

        function triggerUpdate()
        {
          var operation = new Operation({ action: "trigger update",
                                          url: "triggertrackedbranchupdate",
                                          data: { branch_id: branch_id }});
          var result = operation.execute();

          if (result)
            dialog.dialog("close");
        }

        function disable()
        {
          function finish()
          {
            confirm.dialog("close");

            var operation = new Operation({ action: "disable tracking",
                                            url: "disabletrackedbranch",
                                            data: { branch_id: branch_id }});
            var result = operation.execute();

            if (result)
            {
              dialog.dialog("close");
              branch_row.find("td.enabled").text("No");
            }
          }

          var confirm = $("<div title='Disable Branch Tracking'><p>Are you sure you want to disable the tracking of this branch?</p></div>");

          confirm.dialog({ buttons: { "Disable the tracking": finish,
                                      "Do nothing": function () { confirm.dialog("close"); }}});
        }

        function enable()
        {
          var operation = new Operation({ action: "enable tracking",
                                          url: "enabletrackedbranch",
                                          data: { branch_id: branch_id }});
          var result = operation.execute();

          if (result)
          {
            dialog.dialog("close");
            branch_row.find("td.enabled").text("Yes");
          }
        }

        function deleteTrackedBranch()
        {
          function finish()
          {
            confirm.dialog("close");

            var operation = new Operation({ action: "delete tracking",
                                            url: "deletetrackedbranch",
                                            data: { branch_id: branch_id }});
            var result = operation.execute();

            if (result)
            {
              dialog.dialog("close");
              branch_row.remove();
            }
          }

          var confirm = $("<div title='Delete Branch Tracking'><p>Are you sure you want to delete the tracking of this branch?</p></div>");

          confirm.dialog({ buttons: { "Delete the tracking": finish,
                                      "Do nothing": function () { confirm.dialog("close"); }}});
        }

        var buttons = {};

        if (user_ids.indexOf(user.id) != -1 || user.administrator)
        {
          if (branch_row.find("td.enabled").text() == "Yes")
          {
            buttons["Update now"] = triggerUpdate;
            buttons["Disable"] = disable;
          }
          else if (branch_row.find("td.enabled").text() == "No")
            buttons["Enable"] = enable;

          buttons["Delete"] = deleteTrackedBranch;
        }

        buttons["Close"] = function () { dialog.dialog("close"); };

        dialog.dialog({ width: 600, buttons: buttons });

        ev.preventDefault();
      });
  });

function addTrackedBranch(repository_id)
{
  var repository = repositories[repository_id];

  var dialog = $("<div title='Add Tracked Branch' id=addtrackedbranch>" +
                 "<table>" +
                 "<tr><td class=key>Source repository:</td>" +
                 "<td class=value><input id=sourcelocation value='" + htmlify(repository.defaultRemoteLocation) + "'></td></tr>" +
                 "<tr><td class=key></td><td class=note>Source repository location/URL.</td></tr>" +
                 "<tr><td class=key>Source branch name:</td><td class=value><input id=sourcename></td></tr>" +
                 "<tr><td class=key></td><td class=note>Name of the branch in the source repository, without the leading \"refs/heads/\".</td></tr>" +
                 "<tr><td class=key>Target repository:</td><td class=value>" + htmlify(repository.location) + "</td></tr>" +
                 "<tr><td class=key>Target branch name:</td><td class=value><input id=targetname></td></tr>" +
                 "<tr><td class=key></td><td class=note>Name of the branch in Critic's repository, without the leading \"refs/heads/\".</td></tr>" +
                 "<tr><td class=key>Users:</td><td class=value><input id=users value='" + htmlify(user.name) + "'></td></tr>" +
                 "<tr><td class=key></td><td class=note>Space or comma separated list of users to send emails to if the tracking fails.</td></tr>" +
                 "</div>");

  var sourcename = dialog.find("#sourcename");
  var targetname = dialog.find("#targetname");

  sourcename.change(
    function ()
    {
      if (targetname.val() == "")
        targetname.val(sourcename.val());
    });

  function finish()
  {
    var source_location = dialog.find("#sourcelocation").val().trim();
    var source_name = dialog.find("#sourcename").val().trim();
    var target_name = dialog.find("#targetname").val().trim();
    var users = dialog.find("#users").val().split(/\s*,\s*|\s+/g);
    var errors = [];

    if (source_location == "")
      errors.push("Empty source repository.");

    if (source_name == "")
      errors.push("Empty source branch name.");

    if (target_name == "")
      errors.push("Empty target branch name.");

    if (errors.length == 0)
    {
      var operation = new Operation({ action: "add tracked branch",
                                      url: "addtrackedbranch",
                                      data: { repository_id: repository_id,
                                              source_location: source_location,
                                              source_name: source_name,
                                              target_name: target_name,
                                              users: users }});

      var result = operation.execute();

      if (result)
      {
        dialog.dialog("close");
        location.reload();
      }
    }
    else
      alert(errors.join("\n"));
  }

  function cancel()
  {
    dialog.dialog("close");
  }

  var buttons = { "Add Tracked Branch": finish, "Cancel": cancel };

  dialog.dialog({ width: 600, buttons: buttons });

  if (repository.defaultRemoteLocation)
    dialog.find("#sourcename").focus();
  else
    dialog.find("#sourcelocation").focus();
}
