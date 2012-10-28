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

function installExtension(author_name, extension_name, version)
{
  $("button").each(function (index, button) { button.disabled = true; });

  var operation = new Operation({ action: "install extension",
                                  url: "installextension",
                                  data: { author_name: author_name,
                                          extension_name: extension_name,
                                          version: version }});
  var result = operation.execute();

  if (result)
    showMessage("Extension installed!", extension_name + " installed!", "The extension was installed successfully.", function () { location.reload(); });
}

function uninstallExtension(author_name, extension_name)
{
  $("button").each(function (index, button) { button.disabled = true; });

  var operation = new Operation({ action: "uninstall extension",
                                  url: "uninstallextension",
                                  data: { author_name: author_name,
                                          extension_name: extension_name }});
  var result = operation.execute();

  if (result)
    location.reload();
}

function reinstallExtension(author_name, extension_name, version)
{
  $("button").each(function (index, button) { button.disabled = true; });


  var operation = new Operation({ action: "reinstall extension",
                                  url: "reinstallextension",
                                  data: { author_name: author_name,
                                          extension_name: extension_name,
                                          version: version }});
  var result = operation.execute();

  if (result)
    location.reload();
}

$(function ()
  {
    $("a.button").button();

    $("select.details").change(function (ev)
      {
        var select = $(ev.currentTarget);
        var previous = JSON.stringify(selected_versions);
        var value = select.val();
        var key = select.attr("critic-author") + "/" + select.attr("critic-extension");

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
