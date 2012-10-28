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

"use strict";

function restartService(service_name)
{
  var operation = new Operation({ action: "restart service",
				  url: "restartservice",
				  data: { service_name: service_name },
				  wait: "Restarting service..." });

  if (operation.execute())
    location.reload();
}

function getServiceLog(service_name)
{
  var content;

  function resize()
  {
    var pre = content.find("pre");
    var available = content.innerHeight();

    available -= parseInt(content.css("padding-top")) + parseInt(content.css("padding-bottom"));
    available -= parseInt(pre.css("margin-top")) + parseInt(pre.css("margin-bottom"));
    available -= parseInt(pre.css("border-top")) + parseInt(pre.css("border-bottom"));

    pre.height(available);
  }

  var operation = new Operation({ action: "fetch service log",
				  url: "getservicelog",
				  data: { service_name: service_name },
				  wait: "Fetching service log..." });
  var result = operation.execute();

  if (result)
  {
    content = $("<div class='servicelog' title='Service Log'><pre>" + htmlify(result.lines.join("\n")) + "</pre></div>");

    content.dialog({ width: Math.min($(document).width() - 100, 1024),
		     buttons: { Close: function () { content.dialog("close"); }},
		     resize: resize });

    resize();
  }
}