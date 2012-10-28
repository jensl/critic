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

/* -*- Mode: text; indent-tabs-mode: nil -*- */

"use strict";

function search()
{
  var summary = document.getElementsByName("summary")[0].value;
  var summary_mode = document.getElementsByName("summary_mode")[0].value;
  var branch = document.getElementsByName("branch")[0].value;
  var owner = document.getElementsByName("owner")[0].value;
  var path = document.getElementsByName("path")[0].value;
  var parameters = [];

  if (summary)
  {
    parameters.push("summary=" + encodeURIComponent(summary));
    parameters.push("summarymode=" + encodeURIComponent(summary_mode));
  }

  if (branch)
    parameters.push("branch=" + encodeURIComponent(branch));

  if (owner)
    parameters.push("owner=" + encodeURIComponent(owner));

  if (path)
    parameters.push("path=" + encodeURIComponent(path));

  if (parameters.length)
    location.search = parameters.join("&");
}

$(function ()
  {
    $("input[name='owner']").autocomplete({ source: users });
  });
