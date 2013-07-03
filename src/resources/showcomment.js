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

keyboardShortcutHandlers.push(function (key)
  {
    for (var chain_id = null in commentChainById)
      break;

    if (chain_id === null)
      return false;

    if (key == "m".charCodeAt(0))
      contextLines = Math.ceil(contextLines * 1.5) || 1;
    else if (key == "l".charCodeAt(0))
      contextLines = Math.floor(contextLines / 1.5);
    else
      return false;

    location.replace("/showcomment?chain=" + chain_id + "&context=" + contextLines);
    return true;
  });

$(document).keypress(function (ev)
  {
    if (ev.ctrlKey || ev.shiftKey || ev.altKey || ev.metaKey || !ev.which || !keyboardShortcuts)
      return;

    if (/^(?:input|textarea)$/i.test(ev.target.nodeName))
      if (ev.keyCode == 32 || /textarea/i.test(ev.target.nodeName) || !/^(?:checkbox|radio)$/i.test(ev.target.type))
        return;

    if (handleKeyboardShortcut(ev.keyCode))
      ev.preventDefault();
  });
