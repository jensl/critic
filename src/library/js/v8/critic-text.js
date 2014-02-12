/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2013 Jens Lindström, Opera Software ASA

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

function reflow(text, line_length, indent)
{
  text = text.replace("\r", "\n");
  indent = indent || "";

  /* Zero line-length means reflowing is disabled (by user configuration.) */
  if (line_length == 0)
    return text;

  var paragraphs = text.split(/\n\n+/g);

paragraph_loop:
  for (var pindex = 0; pindex < paragraphs.length; ++pindex)
  {
    var lines = paragraphs[pindex].split("\n");

    for (var lindex = 0; lindex < lines.length; ++lindex)
    {
      var line = lines[lindex];
      if (/^[ \t\-*]/.test(line) || lindex != lines.length - 1 && line.length < line_length * .5)
      {
        /* Paragraph seems to be something other than plain text; don't reflow. */
        if (indent)
          paragraphs[pindex] = lines.map(function (line) { return indent + line; }).join("\n");
        continue paragraph_loop;
      }
    }

    var new_lines = [];
    var new_line = indent;
    var words = paragraphs[pindex].split(/(\s+)/g);
    var ws = "";

    for (var windex = 0; windex < words.length; ++windex)
    {
      var word = words[windex];
      if (!word.trim())
        if (word.indexOf("\n") != -1)
          ws = " ";
        else
          ws = word;
      else
      {
        if (new_line != indent)
          if (new_line.length + ws.length + word.length > line_length)
          {
            new_lines.push(new_line);
            new_line = indent;
          }
          else
            new_line += ws;

        new_line += word;
      }
    }

    if (new_line)
      new_lines.push(new_line);

    paragraphs[pindex] = new_lines.join("\n");
  }

  return paragraphs.join(format("\n%s\n", indent.trim()));
}

function repeat(s, n)
{
  return Array(n + 1).join(s);
}

function spaces(n)
{
  return repeat(" ", n);
}

/* items = [(path, deleted, inserted), ...] */
function renderFilesLines(items, indent)
{
  items = items.slice().sort(function (x, y) { x = x[0]; y = y[0]; switch (true) { case x < y: return -1; case x > y: return 1; default: return 0; } });

  var path_width = Math.max.apply(null, items.map(function (item) { return item[0].length; }));
  var delete_max = Math.max.apply(null, items.map(function (item) { return item[1]; }));
  var delete_width = delete_max ? String(delete_max).length : 0;
  var insert_max = Math.max.apply(null, items.map(function (item) { return item[2]; }));
  var insert_width = insert_max ? String(insert_max).length : 0;

  function renderLines(item)
  {
    var result;

    if (item[1])
      result = format("%s-%d", spaces(delete_width - String(item[1]).length), item[1]);
    else if (item[2])
      result = spaces(delete_width + 1);

    if (item[2])
      result += format(" %s+%d", spaces(insert_width - String(item[2]).length), item[2]);

    return result;
  }

  var item = items[0];
  var path = item[0];
  var result = format("%s%s%s %s\n", indent, path, spaces(path_width - path.length), renderLines(item));
  var previous = path.split("/");

  for (var iindex = 1; iindex < items.length; ++iindex)
  {
    item = items[iindex];
    path = item[0];

    var components = path.split("/");
    var common_prefix_length = 0;

    for (var cindex = 0, ccount = Math.min(previous.length, components.length); cindex < ccount; ++cindex)
      if (previous[cindex] == components[cindex])
        common_prefix_length += 1 + components[cindex].length;
      else
        break;

    if (common_prefix_length > 4)
      path = format("%s.../%s", spaces(common_prefix_length - 4), path.substring(common_prefix_length));

    result += format("%s%s%s %s\n", indent, path, spaces(path_width - path.length), renderLines(item));

    previous = components;
  }

  return result;
}
