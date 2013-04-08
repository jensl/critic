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

function saveFullname()
{
  var input = $("#user_fullname");
  var status = $("#status_fullname");

  var value = input.val().trim();

  if (value == user.displayName)
    status.text("Value not changed");
  else if (!value)
    status.text("Empty name not saved");
  else
  {
    var operation = new Operation({ action: "save changes",
                                    url: "setfullname",
                                    data: { user_id: user.id,
                                            value: value }});

    if (operation.execute())
    {
      status.text("Value saved");
      user.displayName = value;
    }
  }
}

function resetFullname()
{
  var input = $("#user_fullname");
  var status = $("#status_fullname");

  input.val(user.displayName);
  status.text("");
}

function saveEmail()
{
  var input = $("#user_email");
  var status = $("#status_email");

  var value = input.val().trim();

  if (value == user.email)
    status.text("Value not changed");
  else if (!value)
    status.text("Empty name not saved");
  else
  {
    var operation = new Operation({ action: "save changes",
                                    url: "setemail",
                                    data: { user_id: user.id,
                                            value: value }});

    if (operation.execute())
    {
      status.text("Value saved");
      user.email = value;
    }
  }
}

function resetEmail()
{
  var input = $("#user_email");
  var status = $("#status_email");

  input.val(user.email);
  status.text("");
}

function saveGitEmails()
{
  var input = $("#user_gitemails");
  var status = $("#status_gitemails");

  var value = input.val().trim();

  if (value == user.gitEmails)
    status.text("Value not changed");
  else if (!value)
    status.text("Empty name not saved");
  else
  {
    var operation = new Operation({ action: "save changes",
                                    url: "setgitemails",
                                    data: { user_id: user.id,
                                            value: value.split(/,\s*|\s+/g) }});

    if (operation.execute())
    {
      status.text("Value saved");
      user.gitEmails = value;
    }
  }
}

function resetGitEmails()
{
  var input = $("#user_gitemails");
  var status = $("#status_gitemails");

  input.val(user.gitEmails);
  status.text("");
}

function changePassword()
{
  var dialog;

  if (administrator)
    dialog = $("<div class=password title='Change password'>"
               +   "<p><b>New password:</b><br>"
               +     "<input class=new1 type=password><br>"
               +     "<input class=new2 type=password>"
               +   "</p>"
               + "</div>");
  else
    dialog = $("<div class=password title='Change password'>"
               +   "<p><b>Current password:</b><br>"
               +     "<input class=current type=password>"
               +   "</p>"
               +   "<p><b>New password:</b><br>"
               +     "<input class=new1 type=password><br>"
               +     "<input class=new2 type=password>"
               +   "</p>"
               + "</div>");

  function save()
  {
    var new1 = dialog.find("input.new1").val();
    var new2 = dialog.find("input.new2").val();

    if (new1 != new2)
    {
      showMessage("Invalid input", "New password mismatch!", "The new password must be input twice.");
      return;
    }

    var data = { user_id: user.id, new_pw: new1 };

    if (!administrator)
    {
      var current = dialog.find("input.current").val();

      if (!current)
      {
        showMessage("Invalid input", "Current password empty!", "The current password must be input.");
        return;
      }

      data.current_pw = current;
    }

    var operation = new Operation({ action: "change password",
                                    url: "changepassword",
                                    data: data });

    if (operation.execute())
    {
      dialog.dialog("close");
      showMessage("Success", "Password changed!");
    }
  }

  function cancel()
  {
    dialog.dialog("close");
  }

  dialog.dialog({ width: 400, buttons: { "Save": save, "Cancel": cancel }});
}

function ModificationChecker(current, input, status)
{
  var is_modified_last = false;

  setInterval(
    function ()
    {
      var is_modified_now = input.val() != current();

      if (is_modified_last != is_modified_now)
      {
        status.text(is_modified_now ? "Modified" : "");

        if (is_modified_now)
          input.nextAll("button").removeAttr("disabled");
        else
          input.nextAll("button").attr("disabled", "disabled");
      }
    }, 100);
}

$(function ()
  {
    var fullname_input = $("#user_fullname");
    var fullname_status = $("#status_fullname");

    if (fullname_input.size() && fullname_status.size())
      new ModificationChecker(function () { return user.displayName; }, fullname_input, fullname_status);

    var email_input = $("#user_email");
    var email_status = $("#status_email");

    if (email_input.size() && email_status.size())
      new ModificationChecker(function () { return user.email; }, email_input, email_status);

    var gitemails_input = $("#user_gitemails");
    var gitemails_status = $("#status_gitemails");

    if (gitemails_input.size() && gitemails_status.size())
      new ModificationChecker(function () { return user.gitEmails; }, gitemails_input, gitemails_status);
  });

function deleteFilterById(filter_id)
{
  var operation = new Operation({ action: "delete filter",
                                  url: "deletefilter",
                                  data: { filter_id: filter_id }});

  return !!operation.execute();
}

function editFilter(repository_name, filter_id, filter_type, filter_path, filter_delegates)
{
  function getPaths(prefix, callback)
  {
    var repository_name = repository.val();

    if (repository_name != "-")
    {
      var operation = new Operation({ action: "fetch path suggestions",
                                      url: "getrepositorypaths",
                                      data: { prefix: prefix,
                                              repository_name: repository_name },
                                      callback: function (result)
                                                {
                                                  if (result)
                                                    callback(result.paths, true);
                                                }});
      operation.execute();
      return operation;
    }
    else
      return null;
  }

  if (typeof no_repositories != "undefined")
  {
    /* There are no repositories. */

    showMessage("Impossible!", "No repositories",
                ("There are no repositories in this Critic system, and it is " +
                 "consequently impossible to create filters.  You might want to " +
                 "<a href=/newrepository>add a repository</a>."));
    return;
  }

  var dialog = $("div.hidden > div.filterdialog").clone();

  if (filter_id)
    dialog.attr("title", "Edit Filter");
  else
    dialog.attr("title", "Add Filter");

  var repository = dialog.find("select[name='repository']");
  var type = dialog.find("select[name='type']");
  var path = dialog.find("input[name='path']");
  var matchedfiles = dialog.find("span.matchedfiles");
  var delegates = dialog.find("input[name='delegates']");
  var apply = dialog.find("input[name='apply']");

  var matchedfiles_repository = null;
  var matchedfiles_path = null;
  var matchedfiles_error = null;

  matchedfiles.click(
    function ()
    {
      if (matchedfiles_error)
        showMessage("Error", "Invalid pattern!", matchedfiles_error);
      else if (matchedfiles_repository && matchedfiles_path)
        showMatchedFiles(matchedfiles_repository, matchedfiles_path);
    });

  function updateMatchedFiles()
  {
    if (repository.val() == "-")
      return;

    var repository_value = repository.val();
    var path_value = path.val().trim();

    function update(result)
    {
      if (result)
      {
        matchedfiles.text("Matches " + result.count + " file" + (result.count == 1 ? "" : "s"));
        if (result.count != 0)
        {
          matchedfiles.addClass("clickable");
          matchedfiles_repository = repository_value;
          matchedfiles_path = path_value;
        }
        else
        {
          matchedfiles.removeClass("clickable");
          matchedfiles_repository = matchedfiles_path = null;
        }
        matchedfiles_error = null;
      }
    }

    function invalid(result)
    {
      matchedfiles.text("Invalid pattern!");
      matchedfiles.addClass("clickable");
      matchedfiles_repository = matchedfiles_path = null;
      matchedfiles_error = result.message;
      return true;
    }

    if (path_value && path_value != "/")
    {
      var operation = new Operation({ action: "count matched files",
                                      url: "countmatchedpaths",
                                      data: { single: { repository_name: repository.val(),
                                                        path: path_value }},
                                      callback: update,
                                      failure: { invalidpattern: invalid }});

      operation.execute();
    }
    else
    {
      matchedfiles.text("Matches all files.");
      matchedfiles.removeClass("clickable");
      matchedfiles_repository = matchedfiles_path = null;
      matchedfiles_error = null;
    }
  }

  if (filter_id !== void 0)
  {
    repository.val(repository_name);
    type.val(filter_type);
    path.val(filter_path);
    delegates.val(filter_delegates);

    if (filter_type != "reviewer")
      delegates.attr("disabled", "disabled");

    updateMatchedFiles();
  }
  else
  {
    type.val("reviewer");
    path.val("");
    path.autocomplete({ source: AutoCompletePath(getPaths), html: true });
    delegates.val("");
    delegates.removeAttr("disabled");
  }

  function saveFilter()
  {
    var type_value = type.val();
    var path_value = path.val().trim() || "/";
    var delegates_value;

    if (type_value == "reviewer")
      delegates_value = delegates.val().trim().split(/\s*,\s*|\s+/g);
    else
      delegates_value = [];

    if (repository.val() == "-")
    {
      showMessage("Invalid input", "No repository selected!", "Please select a repository.",
                  function () { repository.focus(); });
      return;
    }

    var data = { filter_type: type_value,
                 path: path_value,
                 delegates: delegates_value,
                 repository_name: repository.val() };

    if (filter_id !== void 0)
      data.replaced_filter_id = filter_id;

    var operation = new Operation({ action: "save filter",
                                    url: "addfilter",
                                    data: data });
    var result = operation.execute();

    if (result)
    {
      var do_apply = apply.is(":checked");
      dialog.dialog("close");
      if (do_apply)
        reapplyFilters(result.filter_id, true);
      else
        location.reload();
    }
  }

  function deleteFilter()
  {
    if (deleteFilterById(filter_id))
    {
      dialog.dialog("close");
      location.reload();
    }
  }

  function closeDialog()
  {
    dialog.dialog("close");
  }

  var buttons = {};

  buttons["Save"] = saveFilter;

  if (filter_id)
  {
    buttons["Delete"] = deleteFilter;
    buttons["Close"] = closeDialog;
  }
  else
    buttons["Cancel"] = closeDialog;

  dialog.dialog({ width: 600, buttons: buttons });

  if (repository.val() == "-")
    repository.focus();
  else
    path.focus();

  function handleKeypress(ev)
  {
    if (ev.keyCode == 13)
      saveFilter();
  }

  path.keypress(handleKeypress);
  delegates.keypress(handleKeypress);

  path.change(updateMatchedFiles);

  type.change(
    function ()
    {
      if (type.val() == "reviewer")
        delegates.removeAttr("disabled");
      else
        delegates.attr("disabled", "disabled");
    });
}

function showMatchedFiles(repository_name, path)
{
  function finished(result)
  {
    if (result)
    {
      var options = [];

      for (var index = 0; index < result.paths.length; ++index)
      {
        options.push("<option>" + htmlify(result.paths[index]) + "</option>");
      }

      var dialog = $("<div class=matchedfiles><select multiple>" + options.join("") + "</select></div>");

      dialog.attr("title", options.length + " file" + (options.length != 1 ? "s" : "") + " matched by " + path);
      dialog.find("select").attr("size", Math.min(20, options.length));
      dialog.dialog({ width: 600, buttons: { "Close": function () { dialog.dialog("close"); }}});
    }
  }

  var operation = new Operation({ action: "fetch matched paths",
                                  url: "getmatchedpaths",
                                  data: { repository_name: repository_name,
                                          path: path },
                                  wait: "Fetching matched paths...",
                                  cancelable: true,
                                  callback: finished });

  operation.execute();
}

function reapplyFilters(filter_id, reload_when_finished)
{
  function finished(result)
  {
    if (result && filter_id === void 0)
    {
      var changes, first;

      if (result.assigned_reviews.length == 0 &&
          result.watched_reviews.length == 0)
        changes = "<tr><th colspan=2>No changes.</th></tr>";
      else
      {
        changes = "";

        if (result.assigned_reviews.length > 0)
        {
          changes += "<tr><th colspan=2>Reviews with new changes to review:</th></tr>";
          first = " class=first";

          result.assigned_reviews.forEach(
            function (review_id)
            {
              changes += "<tr" + first + "><td class=id><a href=r/" + review_id + ">r/" + review_id + "</a></td><td class=summary>" + htmlify(result.summaries[review_id]) + "</td></tr>";
              first = "";
            });
        }

        if (result.watched_reviews.length > 0)
        {
          changes += "<tr><th colspan=2>New watched reviews:</th></tr>";
          first = " class=first";

          result.watched_reviews.forEach(
            function (review_id)
            {
              changes += "<tr" + first + "><td><a href=r/" + review_id + ">r/" + review_id + "</a></td><td>" + htmlify(result.summaries[review_id]) + "</td></tr>";
              first = "";
            });
        }
      }

      var dialog = $("<div class=reapplyresult>"
                   +   "<h1>Result:</h1>"
                   +   "<table>"
                   +     changes
                   +   "</table>"
                   + "</div>");

      dialog.dialog({ width: 800,
                      buttons: { Close: function () { dialog.dialog("close"); }},
                      close: function () { if (reload_when_finished) location.reload(); }});
    }
    else if (reload_when_finished)
      location.reload();
  }

  var operation = new Operation({ action: "reapply filters",
                                  url: "reapplyfilters",
                                  data: { filter_id: filter_id },
                                  wait: "Please wait...",
                                  callback: finished });

  operation.execute();
}

function countMatchedFiles()
{
  if (count_matched_files.length == 0)
    return;

  var item = count_matched_files.shift();

  function update(result)
  {
    if (result)
    {
      result.filters.forEach(
        function (filter)
        {
          var link = $("#f" + filter.id);
          if (filter.count)
            link.text(filter.count + " file" + (filter.count == 1 ? "" : "s"));
          else
            link.replaceWith("no files")
        });
      countMatchedFiles();
    }
  }

  var operation = new Operation({ action: "count matched files",
                                  url: "countmatchedpaths",
                                  data: { multiple: item },
                                  callback: update });

  operation.execute();
}

$(function ()
  {
    countMatchedFiles();
  });
