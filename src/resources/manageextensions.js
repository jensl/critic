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

function installExtension(author_name, extension_name, version, universal)
{
  $("button").prop("disabled", true);

  var data = { extension_name: extension_name,
               version: version,
               universal: Boolean(universal) };

  if (author_name)
    data.author_name = author_name;

  var operation = new Operation({ action: "install extension",
                                  url: "installextension",
                                  data: data });
  var result = operation.execute();

  if (result)
    showMessage("Extension installed!",
                extension_name + " installed!",
                "The extension was installed successfully.",
                function () { location.reload(); });
}

function uninstallExtension(author_name, extension_name, universal)
{
  $("button").prop("disabled", true);

  var data = { extension_name: extension_name,
               universal: Boolean(universal) };

  if (author_name)
    data.author_name = author_name;

  var operation = new Operation({ action: "uninstall extension",
                                  url: "uninstallextension",
                                  data: data });
  var result = operation.execute();

  if (result)
    location.reload();
}

function reinstallExtension(author_name, extension_name, version, universal)
{
  $("button").prop("disabled", true);

  var data = { extension_name: extension_name,
               version: version,
               universal: Boolean(universal) };

  if (author_name)
    data.author_name = author_name;

  var operation = new Operation({ action: "reinstall extension",
                                  url: "reinstallextension",
                                  data: data });
  var result = operation.execute();

  if (result)
    location.reload();
}

function clearExtensionStorage(author_name, extension_name)
{
  function clear()
  {
    var data = { extension_name: extension_name };

    if (author_name)
      data.author_name = author_name;

    var operation = new Operation({ action: "clear extension storage",
                                    url: "clearextensionstorage",
                                    data: data });

    if (operation.execute()) {
      close();
      location.reload();
    }
  }

  function close()
  {
    dialog.dialog("close");
  }

  var dialog = $(
    "<div title='Please confirm'>" +
    "<p>Clearing an extension's storage deletes whatever state the extension " +
    "has stored about your use of it since you first installed it.  The " +
    "state can not be restored!</p><p><b>Are you sure?</b></p>" +
    "</div>");

  dialog.dialog({
    width: 600,
    modal: true,
    buttons: {
      "Clear storage": clear,
      "Do nothing": close
    }
  });
}

$(function ()
  {
    $("a.button").button();

    $("select.details").change(function (ev)
      {
        var select = $(ev.currentTarget);
        var previous = JSON.stringify(selected_versions);
        var value = select.val();
        var author_name = select.attr("critic-author");
        var extension_name = select.attr("critic-extension");
        var key;

        if (author_name)
          key = author_name + "/" + extension_name;
        else
          key = extension_name;

        if (!value)
          delete selected_version[key];
        else if (value == "live")
          selected_versions[key] = null;
        else
          /* value = "version/*" */
          selected_versions[key] = value.substring(8);

        var next = JSON.stringify(selected_versions);

        if (next != previous)
        {
          /* Restore state before we leave the page: */
          selected_versions = JSON.parse(previous);

          location.href = "/manageextensions?select=" + encodeURIComponent(next) + "&focus=" + encodeURIComponent(key);
        }
      });
  });
