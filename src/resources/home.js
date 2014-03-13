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
                                    data: { subject_id: user.id,
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

function setPassword()
{
  var dialog = $("<div class=password title='Set password'>"
               +   "<p><b>New password:</b><br>"
               +     "<input id=newpw1 type=password>"
               +   "</p>"
               +   "<p><b>New password, again:</b><br>"
               +     "<input id=newpw2 type=password>"
               +   "</p>"
               + "</div>");

  function save()
  {
    var newpw1 = $("#newpw1").val();
    var newpw2 = $("#newpw2").val();

    if (newpw1 != newpw2)
    {
      showMessage("Invalid input",
                  "New password mismatch!",
                  "The new password must be input twice.");
      return;
    }

    var operation = new Operation({ action: "set password",
                                    url: "changepassword",
                                    data: { subject: user.id,
                                            new_pw: newpw1 }});

    if (operation.execute())
    {
      dialog.dialog("close");
      showMessage("Success", "Password set!", null, function () { location.reload(); });
    }
  }

  function cancel()
  {
    dialog.dialog("close");
  }

  dialog.find("input").keypress(
    function (ev)
    {
      if (ev.keyCode == 13)
      {
        if ($("#newpw1").is(":focus"))
          $("#newpw2").focus();
        else if ($("#newpw2").is(":focus"))
          save();
      }
    });

  dialog.dialog({ width: 400,
                  modal: true,
                  buttons: { "Save": save, "Cancel": cancel }});

  $("newpw1").focus();
}

function changePassword()
{
  var dialog = $("<div class=password title='Change password'>"
               +   "<p><b>Current password:</b><br>"
               +     "<input id=currentpw type=password>"
               +   "</p>"
               +   "<p><b>New password:</b><br>"
               +     "<input id=newpw1 type=password>"
               +   "</p>"
               +   "<p><b>New password, again:</b><br>"
               +     "<input id=newpw2 type=password>"
               +   "</p>"
               + "</div>");

  function save()
  {
    var currentpw = $("#currentpw").val();
    var newpw1 = $("#newpw1").val();
    var newpw2 = $("#newpw2").val();

    if (newpw1 != newpw2)
    {
      showMessage("Invalid input",
                  "New password mismatch!",
                  "The new password must be input twice.");
      return;
    }

    var operation = new Operation({ action: "change password",
                                    url: "changepassword",
                                    data: { subject: user.id,
                                            current_pw: currentpw,
                                            new_pw: newpw1 } });

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

  dialog.find("input").keypress(
    function (ev)
    {
      if (ev.keyCode == 13)
      {
        if ($("#currentpw").is(":focus"))
          $("#newpw1").focus();
        else if ($("#newpw1").is(":focus"))
          $("#newpw2").focus();
        else if ($("#newpw2").is(":focus"))
          save();
      }
    });

  dialog.dialog({ width: 400,
                  modal: true,
                  buttons: { "Save": save, "Cancel": cancel }});

  $("#currentpw").focus();
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
        input.nextAll("button").prop("disabled", !is_modified_now);
      }
    }, 100);
}

function showUnverifiedAddressDialog(ev) {
  ev.preventDefault();

  var context = $(this).closest(".address");
  var address = context.find(".value").text();
  var content = $("<div class='unverified-dialog' title='Unverified email address'>" +
                  "<p>The address <span class='address inset'>" + htmlify(address) +
                  "</span> needs to be verified as valid and in your control. " +
                  "A verification email has been sent to the address already " +
                  "and should arrive shortly.</p>" +
                  "<p>If you suspect it has been lost in transit, you can " +
                  "request another one.</p>" +
                  "</div>");

  function sendVerificationEmail() {
    var operation = new Operation({
      action: "request verification email",
      url: "requestverificationemail",
      data: {
        email_id: context.data("email-id")
      }
    });

    if (operation.execute())
      content.dialog("close");
  }

  function close() {
    content.dialog("close");
  }

  content.dialog({
    modal: true,
    width: 600,
    buttons: {
      "Send verification email": sendVerificationEmail,
      "Close": close
    }
  });
}

function showDeleteAddressDialog(ev) {
  ev.preventDefault();

  var context = $(this).closest(".address");
  var is_current = context.is(".selected");

  function deleteAddress(dialog) {
    var operation = new Operation({
      action: "delete address",
      url: "deleteemailaddress",
      data: {
        email_id: context.data("email-id")
      }
    });

    if (operation.execute()) {
      if (dialog)
        dialog.dialog("close");
      location.reload();
    }
  }

  if (is_current) {
    if (context.closest(".addresses").children(".address").size() > 1) {
      showMessage("Not allowed", "Will not delete current address",
                  "This email address is your current address.  Please select " +
                  "one of the other addresses as your current address before " +
                  "deleting it.");
      return;
    } else {
      var content =
        $("<div class='delete-current-dialog' title='Delete current address?'>" +
          "<p>Deleting your current email address means Critic will " +
          "stop sending emails to you.  Are you sure you want that?</p>" +
          "</div>");

      content.dialog({
        modal: true,
        width: 600,
        buttons: {
          "Delete address": function () {
            deleteAddress(content);
          },
          "Do nothing": function () {
            content.dialog("close");
          }
        }
      });
    }
  } else {
    deleteAddress();
  }
}

function showSelectEmailAddressDialog(ev) {
  var context = $(this).closest(".address");
  var is_unverified = context.find(".unverified").size() != 0;

  function selectAddress(dialog) {
    var operation = new Operation({
      action: "select address",
      url: "selectemailaddress",
      data: {
        email_id: context.data("email-id")
      }
    });

    if (operation.execute()) {
      context.closest(".addresses")
        .find(".address").not(context).removeClass("selected");
      context.addClass("selected");
      context.find("input").prop("checked", true);

      if (dialog)
        dialog.dialog("close");
    }
  }

  if (is_unverified) {
    var content =
      $("<div class='select-unverified-dialog' title='Select unverified address?'>" +
        "<p>Selecting an unverified email address means Critic will stop " +
        "sending emails to you until the address has been verified.  Are you " +
        "sure you want that?</p>" +
        "</div>");

    content.dialog({
      modal: true,
      width: 600,
      buttons: {
        "Select address": function () {
          selectAddress(content);
        },
        "Do nothing": function () {
          $(".address.selected input").prop("checked", true);
          content.dialog("close");
        }
      }
    });

    ev.preventDefault();
  } else {
    selectAddress();
  }
}

function showAddEmailAddressDialog() {
  var content =
    $("<div class='add-email-dialog' title='Add primary address'>" +
      "<p>Add a primary email address.  You can have several addresses registered, " +
      "but emails will only be sent to the one that is selected.</p>" +
      "</div>");

  if (verifyEmailAddresses) {
    content.append("<p>Note that a verification email will be sent to the added " +
                   "email address, containing a link that must be followed before " +
                   "Critic will send any other emails to the address.</p>");
  }

  content.append("<p><b>Email address:</b><br><input placeholder='user@domain'></p>");

  function isValidAddress() {
    var address = content.find("input").val().trim();
    return /^[^@]+@[^.]+(?:\.[^.]+)*$/.test(address);
  }

  function addAddress() {
    if (!isValidAddress()) {
      showMessage("Invalid email address", "Invalid email address",
                  "That does not look like a valid email address. " +
                  "Please try again.");
    } else {
      var operation = new Operation({
        action: "add email address",
        url: "addemailaddress",
        data: {
          subject_id: user.id,
          email: content.find("input").val().trim()
        }
      });

      if (operation.execute()) {
        content.dialog("close");
        location.reload();
      }
    }
  }

  content.dialog({
    modal: true,
    width: 600,
    buttons: {
      "Add address": function () {
        addAddress();
      },
      "Do nothing": function () {
        content.dialog("close");
      }
    }
  });

  content.find("input").keypress(function (ev) {
    if (ev.keyCode == 13 && isValidAddress())
      addAddress();
  });
}

$(function ()
  {
    var fullname_input = $("#user_fullname");
    var fullname_status = $("#status_fullname");

    if (fullname_input.size() && fullname_status.size())
      new ModificationChecker(function () { return user.displayName; }, fullname_input, fullname_status);

    $(".unverified").click(showUnverifiedAddressDialog);
    $(".delete").click(showDeleteAddressDialog);
    $(".address input").click(showSelectEmailAddressDialog);
    $(".addemail").click(showAddEmailAddressDialog);

    if (/^\?email_verified=\d+/.test(location.search)) {
      if (typeof history.replaceState == "function") {
        var new_url = "/home";
        var match = /&(.+)$/.exec(location.search);
        if (match)
          new_url += "?" + match[1];
        history.replaceState(null, document.title, new_url);
      }
    }

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

    if (repository_name)
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

  dialog.addClass("active");

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
    if (!repository.val())
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
      delegates.prop("disabled", true);

    updateMatchedFiles();
  }
  else
  {
    type.val("reviewer");
    path.val("");
    delegates.val("");
    delegates.prop("disabled", false);
  }

  function saveFilter()
  {
    var type_value = type.val();
    var path_value = path.val().trim();
    var delegates_value;

    if (type_value == "reviewer")
      delegates_value = delegates.val().trim().split(/\s*,\s*|\s+/g);
    else
      delegates_value = [];

    if (!repository.val())
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

  dialog.dialog({ width: 600,
                  modal: true,
                  buttons: buttons });

  dialog.find(".repository-select").chosen({ inherit_select_classes: true });
  dialog.find("select[name='type']").chosen({ disable_search: true });

  if (!repository.val())
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
      delegates.prop("disabled", type.val() != "reviewer");
    });

  path.autocomplete({ source: AutoCompletePath(getPaths),
                      html: true });
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
                                          path: path,
                                          user_id: user.id },
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
              changes += "<tr" + first + "><td class=id><a href=/r/" + review_id + ">r/" + review_id + "</a></td><td class=summary>" + htmlify(result.summaries[review_id]) + "</td></tr>";
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
              changes += "<tr" + first + "><td><a href=/r/" + review_id + ">r/" + review_id + "</a></td><td>" + htmlify(result.summaries[review_id]) + "</td></tr>";
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
  if (typeof count_matched_files == "undefined" || count_matched_files.length == 0)
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
                                  data: { multiple: item,
                                          user_id: user.id },
                                  callback: update });

  operation.execute();
}

$(function ()
  {
    countMatchedFiles();
  });
