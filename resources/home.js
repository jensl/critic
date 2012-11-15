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

if (!Node.prototype.selectNodes)
{
  Node.prototype.selectNodes = function selectNodes(xpathExpr,resolver)
    {
      var arr = [], nodes = (this.ownerDocument || this).evaluate(xpathExpr, this, resolver || null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
      for (var index = 0, node; node = nodes.snapshotItem(index); ++index)
        arr.push(node);
      return arr;
    };

  Node.prototype.selectSingleNode = function selectSingleNode(xpathExpr,resolver)
    {
      return (this.ownerDocument || this).evaluate(xpathExpr, this, resolver || null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
    };
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

function addFilter(button)
{
  var rowAnchor = button.selectSingleNode("ancestor::tr");
  var rowFinal = rowAnchor.parentNode.insertRow(rowAnchor.rowIndex);

  rowFinal.className = "filter";

  var cellType = rowFinal.insertCell(-1);
  var cellPath = rowFinal.insertCell(-1);
  var cellDelegate = rowFinal.insertCell(-1);
  var cellButtons = rowFinal.insertCell(-1);

  cellType.className = "filter type";
  cellType.textContent = "Reviewer";
  cellPath.className = "filter path";
  cellDelegate.className = "filter delegate";
  cellButtons.className = "filter buttons";
  cellButtons.innerHTML = "<input type='button' value='Edit'>";

  editFilter(cellButtons.getElementsByTagName("input")[0], 0, 0, true);
}

function verifyFilterPath(path)
{
  var message = "";
  if (path.length > 1 && path.charAt(0) == "/")
    message += "- Path should not start with a slash.\n";
  if (path.indexOf("*") != -1)
    message += "- Wildcards are currently not supported.\n";
  if (message.length > 0)
  {
    alert("You filter path has issues:\n\n" + message + "\nPlease correct them and try again.");
    return false;
  }
  else
    return true;
}

function editFilter(button, directory_id, file_id, added)
{
  var rowEdit = button.selectSingleNode("ancestor::tr");
  var rowEmpty = rowEdit.selectSingleNode("preceding-sibling::tr[@class='empty']");

  document.getElementById("empty").style.display = "none";

  addClass(rowEdit, "edit");

  var cellType = rowEdit.cells[0];
  var cellPath = rowEdit.cells[1];
  var cellDelegate = rowEdit.cells[2];
  var cellButtons = rowEdit.cells[3];

  var type_value = cellType.textContent;
  var path_value = cellPath.textContent;
  var delegate_value = cellDelegate.textContent;
  var old_buttons = added ? "" : cellButtons.innerHTML;

  cellType.className = "filter type";
  cellType.innerHTML = "<select><option " + (type_value == "Reviewer" ? "selected " : "") + "value='reviewer'>Reviewer</option><option " + (type_value == "Watcher" ? "selected " : "") + "value='watcher'>Watcher</option></select>";
  cellPath.className = "filter path";
  cellPath.innerHTML = "<input value='" + path_value + "'>";
  cellDelegate.className = "filter delegate";
  cellDelegate.innerHTML = "<input value='" + delegate_value + "'>";
  cellButtons.className = "filter buttons";
  cellButtons.innerHTML = "<button>Save</button><button>Cancel</button>";

  var type = cellType.getElementsByTagName("select")[0];
  var path = cellPath.getElementsByTagName("input")[0];
  var delegate = cellDelegate.getElementsByTagName("input")[0];
  var buttons = cellButtons.getElementsByTagName("button");

  $(cellButtons).find("button").button();

  path.onkeypress = function (ev)
    {
      if (ev.keyCode == 13)
      {
        buttons[0].click();
        ev.preventDefault();
      }
    };

  buttons[0].onclick = function saveFilter()
    {
      var type_value = type.value, path_value = path.value, delegate_value = delegate.value;

      if (!verifyFilterPath(path_value))
        return;

      if (!added)
      {
        var xhr = new XMLHttpRequest;

        xhr.open("GET", "deletefilter?repository=" + repository.id + "&directory=" + directory_id + "&file=" + file_id, false);
        xhr.send();

        if (xhr.responseText != "ok")
        {
          alert(xhr.responseText);
          return;
        }
      }

      var xhr = new XMLHttpRequest;

      xhr.open("GET", "addfilter?repository=" + repository.id + "&type=" + type_value + "&path=" + path_value + "&delegate=" + delegate_value, false);
      xhr.send();

      if (xhr.responseText == "error:directory")
        if (confirm("The path entered seems to be a directory, not a file.  Did you mean to filter by directory?"))
        {
          path_value += "/";
          xhr.open("GET", "addfilter?repository=" + repository.id + "&type=" + type_value + "&path=" + path_value + "&delegate=" + delegate_value, false);
          xhr.send();
        }
        else
        {
          xhr.open("GET", "addfilter?repository=" + repository.id + "&type=" + type_value + "&path=" + path_value + "&delegate=" + delegate_value + "&force=yes", false);
          xhr.send();
        }
      else if (/error:invalid-users:.*/.test (xhr.responseText))
      {
        alert("These user names are not valid:\n\n  " + xhr.responseText.substring(20).split(",").join("\n  "));
        return;
      }

      var match = /^ok:directory=(\d+),file=(\d+)$/.exec(xhr.responseText);
      if (match)
      {
        removeClass(rowEdit, "edit");

        var new_directory_id = match[1];
        var new_file_id = match[2];

        cellType.textContent = type_value == "reviewer" ? "Reviewer" : "Watcher";
        cellPath.textContent = path_value;
        cellDelegate.textContent = delegate_value;
        cellButtons.innerHTML = "<button onclick='editFilter(this, " + new_directory_id + ", " + new_file_id + ", false);'>Edit</button><button onclick='deleteFilter(this, " + new_directory_id + ", " + new_file_id + ");'>Delete</button>";
        $(cellButtons).children("button").button();
      }
      else
        alert(xhr.responseText);
    };

  buttons[1].onclick = function cancelFilter()
    {
      if (!rowEdit.selectSingleNode("parent::node()/child::tr[@class='filter']"))
        document.getElementById("empty").style.display = 'inline';

      if (added)
        rowEdit.parentNode.removeChild(rowEdit);
      else
      {
        removeClass(rowEdit, "edit");

        cellType.textContent = type_value;
        cellPath.textContent = path_value;
        cellDelegate.textContent = delegate_value;
        cellButtons.innerHTML = "<button onclick='editFilter(this, " + directory_id + ", " + file_id + ", false);'>Edit</button><button onclick='deleteFilter(this, " + directory_id + ", " + file_id + ");'>Delete</button>";
        $(cellButtons).children("button").button();
      }
    };

  path.focus();
}

function deleteFilter(button, directory_id, file_id)
{
  var rowFilter = button.selectSingleNode("ancestor::tr");
  var rowEmpty = rowFilter.selectSingleNode("preceding-sibling::tr[@class='empty']");

  var xhr = new XMLHttpRequest;

  xhr.open("GET", "deletefilter?repository=" + repository.id + "&directory=" + directory_id + "&file=" + file_id, false);
  xhr.send();

  if (xhr.responseText == "ok")
  {
    rowFilter.parentNode.removeChild(rowFilter);

    if (!rowEmpty.selectSingleNode("following-sibling::tr[@class='filter']"))
      document.getElementById("empty").style.display = 'inline';
  }
  else
    alert(xhr.responseText);
}

$(document).ready(function ()
  {
    $("td.repositories select").change(function (ev)
      {
        if (!repository || ev.target.value != repository.id)
          location.href = "home?repository=" + ev.target.value;
      });
  });
