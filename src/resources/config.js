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

var timer_id = null;
var notifications = {};
var saves_in_progress = 0;

function scheduleSaveSettings()
{
  if (user.id === null)
    /* Don't (try to) save if user is anonymous. */
    return;

  if (timer_id !== null)
    clearTimeout(timer_id);

  timer_id = setTimeout(saveSettings, 500);
}

function saveSettings(reset_item)
{
  if (user.id === null)
    /* Don't (try to) save if user is anonymous. */
    return;

  timer_id = null;

  var data = { settings: [] };
  var per_url = {};

  function processElement(index, element)
  {
    var url = element.getAttribute("critic-url"), value;
    if (url)
    {
      var modified = false;

      if (element instanceof HTMLInputElement)
        if (element.type == "checkbox")
        {
          value = element.checked;
          modified = value !== element.hasAttribute("checked");
          if (modified)
            if (value)
              element.setAttribute("checked", "checked");
            else
              element.removeAttribute("checked");
        }
        else
        {
          value = element.value;
          modified = value !== element.getAttribute("value");
          if (modified)
            element.setAttribute("value", value);
        }
      else
      {
        value = element.value;
        modified = value !== element.getAttribute("critic-value");
        if (modified)
          element.setAttribute("critic-value", value);
      }

      if (!modified)
        return;

      var items = per_url[url];
      if (!items)
      {
        items = per_url[url] = {};
        Object.defineProperty(items, "CRITIC-EXTENSION", { value: element.getAttribute("critic-extension") });
      }
      items[element.getAttribute("name")] = value;

      if (value != JSON.parse(element.getAttribute("critic-default")))
        $(element).parents("tr.line").addClass("customized");
      else
        $(element).parents("tr.line").removeClass("customized");
    }
    else
    {
      if (element.type == "checkbox")
        value = element.checked;
      else if (element.type == "number")
        value = parseInt(element.value);
      else
        value = element.value;

      if (value != JSON.parse(element.getAttribute("critic-current")))
      {
        element.setAttribute("critic-current", JSON.stringify(value));
        data.settings.push({ item: element.name,
                             value: value });
        $(element).parents("tr.line").addClass("customized");
      }
    }
  }

  if (defaults)
    data.user_id = -1;

  if (filter_id !== null)
    data.filter_id = filter_id;
  else if (repository_id !== null)
    data.repository_id = repository_id;

  if (reset_item)
  {
    var element = document.getElementsByName(reset_item)[0];
    var default_value = JSON.parse(element.getAttribute("critic-default"));
    var item = { item: reset_item };

    if (defaults && repository_id === null)
      /* Editing global defaults => reset the default value rather
         than deleting the override. */
      item.value = default_value;

    data.settings.push(item);

    if (element.type == "checkbox")
      element.checked = default_value;
    else
      element.value = default_value;

    $(element).parents("tr.line").removeClass("customized");
    element.setAttribute("critic-current", JSON.stringify(default_value));
  }
  else
    $("td.value > .setting").each(processElement);

  function builtInSaved(result)
  {
    --saves_in_progress;

    if (result)
    {
      if (result.saved_settings.length)
      {
        var title = reset_item ? "Reset to default" : "Saved settings";
        var html = "<b>" + title + ":</b><pre>";

        result.saved_settings.forEach(
          function (item)
          {
            html += htmlify(item) + "\n";
          });

        html += "</pre>";

        if (notifications[html])
          notifications[html].remove();

        notifications[html] = showNotification(
          html, { className: "saved",
                  callback: function () { notifications[html] = null; }});
      }
    }

    for (var url in per_url)
    {
      var items = per_url[url];

      $.ajax({ async: false,
               url: url,
               type: "POST",
               contentType: "text/json",
               data: JSON.stringify(items),
               dataType: "text",
               success: function ()
               {
                 --saves_in_progress;
                 showNotification("saved", "<b>Saved settings for extension " + htmlify(items["CRITIC-EXTENSION"]) + ".</b>");
               },
               error: function (xhr)
               {
                 --saves_in_progress;
                 reportError("save settings for extension " + items["CRITIC-EXTENSION"], "Request failed: " + xhr.responseText);
               }
             });

      ++saves_in_progress;
    }
  }

  if (data.settings.length)
  {
    var operation = new Operation({ action: "save settings",
                                    url: "savesettings",
                                    data: data,
                                    callback: builtInSaved });

    operation.execute();

    ++saves_in_progress;
  }
  else
    builtInSaved();
}

$(document).ready(function ()
  {
    $("input[name='review.createViaPush']").click(function (ev)
      {
        if (ev.target.checked)
          showMessage("Important Note!", "Important Note!", "<p>Please note that when creating a review by pushing a branch whose name starts with <code>r/</code>, only the first (head) commit on the branch will be added to the review, and you will not be able to add its ancestor commits later.</p><p><strong>This feature cannot be used to create a review of multiple commits!</strong></p>");
      });

    $("select.repository").change(function (ev)
      {
        var repository = ev.target.value;
        var params = {};

        if (repository != "-")
          params.repository = repository;

        if (defaults)
          params.defaults = "yes";

        var url = "/config";

        if (Object.keys(params).length)
          url += "?" + Object.keys(params).map(function (name) { return name + "=" + params[name]; }).join("&");

        location.assign(url);
      });

    $("select, input").bind("change input", scheduleSaveSettings);

    window.addEventListener("beforeunload", function (ev)
      {
        saveSettings();

        if (saves_in_progress > 0)
          /* Firefox/IE looks at ev.returnValue; Chrome/Safari looks at the
             function's return value.  Opera either doesn't fire the event
             at all or behaves as Chrome. */
          return ev.returnValue = ("Modified settings are being saved.  You may want " +
                                   "to wait a few seconds before leaving the page.");
      });
  });
