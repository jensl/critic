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

function AutoCompleteUsers(users)
{
  function autocomplete(request, response)
  {
    var match = /^(.*?)([^\s,]*)$/.exec(request.term);
    var source = match[1];
    var term = match[2].toLowerCase();

    if (!term)
    {
      response([]);
      return;
    }

    var matches = [];

    for (var username in users)
    {
      var fullname = users[username];
      if (username.substring(0, term.length).toLowerCase() == term ||
          fullname.substring(0, term.length).toLowerCase() == term)
        matches.push({ label: fullname + " (" + username + ")", value: source + username });
    }

    matches.sort(function (a, b) { switch (true) { case a.label < b.label: return -1; case a.label > b.label: return 1; default: return 0; } });

    response(matches);
  }

  return autocomplete;
}

function AutoCompletePath(paths)
{
  function autocomplete(request, response)
  {
    function hasPrefix(full, prefix)
    {
      return full.substring(0, prefix.length) == prefix;
    }
    function repeat(what, count)
    {
      return Array(count + 1).join(what);
    }

    var matches = [];

    if (request.term)
    {
      var pathnames = Object.keys(paths), previous;

      pathnames.sort();

      for (var index = 0; index < pathnames.length; ++index)
      {
	var pathname = pathnames[index], shortened = pathname;

	if (hasPrefix(pathname, request.term))
	{
	  if (previous)
	  {
	    var components = pathname.split("/"), count = 0, prefix = "", checked_prefix;

	    while (count < components.length && hasPrefix(previous, checked_prefix = components.slice(0, count).join("/")))
	    {
	      ++count;
	      prefix = checked_prefix;
	    }

	    if (prefix.length > 3)
	      shortened = repeat(" ", prefix.length - 3) + "..." + pathname.substring(prefix.length);
	  }

	  var counts = paths[pathname];

	  if (counts[0] == 0)
	    counts = "-" + counts[1] + "/+" + counts[2];
	  else
	    counts = "(" + counts[0] + " files) -" + counts[1] + "/+" + counts[2];

	  matches.push({ label: ("<div class=sourcefont style='padding:0;margin:0;white-space:pre'>" + htmlify(shortened) +
				 "<span style='float:right;font-size:smaller'>" + counts + "</span></div>"),
			 value: pathname });

	  previous = pathname;
	}
	else if (matches.length)
	  break;
      }
    }

    response(matches);
  }

  return autocomplete;
}