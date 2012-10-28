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

function saveResource()
{
  var source = $("textarea").first().val();

  var operation = new Operation({ action: "save resource",
				  url: "storeresource",
				  data: { name: resource_name,
					  source: source },
				  wait: "Saving changes..." });

  if (operation.execute())
    original_source = source;
}

function resetResource()
{
  function proceed()
  {
    var operation = new Operation({ action: "reset resource",
				    url: "resetresource",
				    data: { name: resource_name }});

    return operation.execute() != null;
  }

  var content = $("<div title='Confirm'><p><b>Are you sure you want to stop using your edited resource?</b></p><p>Note that you will be able to switch back to your current edited version later on, unless you save another edited version.</p></div>");

  content.dialog({ modal: true,
                   width: 600,
                   buttons: { "Reset to built-in version": function () { if (proceed()) { content.dialog("close"); location.reload(); }},
                              "Keep edited version": function () { content.dialog("close"); }}});
}

function restoreResource()
{
  var operation = new Operation({ action: "restore resource",
				  url: "restoreresource",
				  data: { name: resource_name }});

  if (operation.execute())
    location.reload();
}

function switchResource(name)
{
  if (name && name != resource_name)
  {
    function switchNow()
    {
      location.replace("editresource?name=" + name);
    }

    $("select").val(resource_name);

    if (resource_name && $("textarea").val() != original_source)
    {
      var content = $("<div title='Save First?'><p>You have edited this resource.  Do you want to save it before selecting another resource?</p></div>");

      content.dialog({ modal: true,
                       width: 600,
                       buttons: { "Save and switch": function () { if (saveResource()) { content.dialog("close"); switchNow(); } },
                                  "Don't switch": function () { content.dialog("close"); },
                                  "Switch without saving": function () { content.dialog("close"); switchNow(); }}});
    }
    else
      switchNow();
  }
  else
    $("select").val(resource_name);
}

$(document).ready(function ()
  {
    $("tr.select td.value select").change(function (ev)
      {
        switchResource(ev.target.value);
      });

    $("button.save").click(saveResource);
    $("button.reset").click(resetResource);
    $("button.restore").click(restoreResource);
  });
