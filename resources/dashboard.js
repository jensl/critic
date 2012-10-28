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

$(document).ready(function ()
  {
    $("h1[title], h2[title]").tooltip({ fade: 250 });

    $("div.main").sortable({
        handle: "td.h1",
        stop: function ()
          {
            if (typeof history.replaceState == "function")
            {
              var items = [];
              $("div.main > table.reviews").each(function (index, element)
                {
                  items.push(element.id);
                });

              var href = location.href.replace(/(?:([?&]show=)[^&#]+|$)/, function (all, group1) { return (group1 ? group1 : "?show=") + items; });

              history.replaceState(null, document.title, href);
            }
          }
      });
  });
