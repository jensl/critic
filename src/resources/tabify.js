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

var tabified = true, tab_width_calculated = false, tabify_style_added = false;

function calculateTabWidth()
{
  if (!tabify_style_added)
  {
    $("head").append('<style>' +
                     '  div.playground { white-space: pre }' +
                     '  b.t:before { content: "\\2192" }' +
                     '  b.t { color: #ccc }' +
                     '  b.t.ill { color: red; font-weight: bold }' +
                     '</style>');

    tabify_style_added = true;
  }

  if (!tab_width_calculated)
  {
    document.write("<div class='playground sourcefont'><span id='playground-space'> </span></div>");

    var playground = $(".playground");
    var space_width = $("#playground-space").width();

    if (space_width != 0)
    {
      var stylesheet = "";

      for (var tabwidth = 2; tabwidth <= 8; ++tabwidth)
      {
        var tab_width_extra = (tabwidth - 1) * space_width; // NOTE: I don't know why " + 1" is necessary.
        var tab_margin_before = (tab_width_extra / 2) << 0;
        var tab_margin_after = tab_width_extra - tab_margin_before;

        stylesheet += "b.w" + tabwidth + " { padding-left: " + tab_margin_before + "px; padding-right: " + tab_margin_after + "px }\n";
      }

      $("head").append("<style>" + stylesheet + "</style>");

      tab_width_calculated = true;
    }

    playground.remove();
  }
}
