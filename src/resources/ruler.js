/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2013 Rafał Chłodnicki, Opera Software ASA

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
    var spaces = (new Array(rulerColumn + 1)).join(" ");
    var space = $('<span class="sourcefont" style="white-space: pre">' + spaces + '</span>');
    $("body").append(space);
    var space_width = space.width();
    space.remove();

    $("head").append('<style>td.line { background-image: url(/static-resource/ruler.png);' +
      'background-position: ' + space_width + 'px 0;' +
      'background-repeat: repeat-y; }</style>');
  });
