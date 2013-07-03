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

function saveSettings()
{
  var data = "";
  var per_url = {};

  $("td.value > .setting").each(function (index, element)
    {
      var url = element.getAttribute("critic-url");
      if (url)
      {
        var modified = false, value;

        if (element instanceof HTMLInputElement)
          if (element.type == "checkbox")
          {
            value = element.checked;
            modified = value !== element.hasAttribute("checked");
          }
          else
          {
            value = element.value;
            modified = value !== element.getAttribute("value");
          }
        else
        {
          value = element.value;
          modified = value !== element.getAttribute("critic-value");
        }

        if (modified)
        {
          var items = per_url[url];
          if (!items)
          {
            items = per_url[url] = {};
            Object.defineProperty(items, "CRITIC-EXTENSION", { value: element.getAttribute("critic-extension") });
          }
          items[element.getAttribute("name")] = value;
        }
      }
      else
        data += element.name + "=" + (element.type == "checkbox" ? (element.checked ? 1 : 0) : $(element).val()) + "\n";
    });

  var wait = $("<div title='Please Wait' style='text-align: center; padding-top: 2em'>Saving settings: <span>built-in</span></div>");

  wait.dialog({ modal: true });

  $.ajax({ async: false,
           url: "savesettings",
           type: "POST",
           contentType: "text/plain",
           data: data,
           dataType: "text",
           success: function (data)
             {
               if (data != "ok")
                 reportError("save settings", "Server reply: <i>" + data + "</i>");
             },
           error: function ()
             {
               reportError("save settings", "Request failed.");
             }
         });

  for (var url in per_url)
  {
    var items = per_url[url];

    wait.find("span").text(items["CRITIC-EXTENSION"]);

    $.ajax({ async: false,
             url: url,
             type: "POST",
             contentType: "text/json",
             data: JSON.stringify(items),
             dataType: "text",
             error: function (xhr)
               {
                 reportError("save settings for extension " + items["CRITIC-EXTENSION"], "Request failed: " + xhr.responseText);
               }
           });
  }

  wait.dialog("close");
}

$(document).ready(function ()
  {
    $("input[name='review.createViaPush']").click(function (ev)
      {
        if (ev.target.checked)
          showMessage("Important Note!", "Important Note!", "<p>Please note that when creating a review by pushing a branch whose name starts with <code>r/</code>, only the first (head) commit on the branch will be added to the review, and you will not be able to add its ancestor commits later.</p><p><strong>This feature cannot be used to create a review of multiple commits!</strong></p>");
      });
  });
