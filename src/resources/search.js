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
  function phrases(value)
  {
    return value.match(/"[^"]+"|'[^']+'|\S+/g).map(
      function (phrase)
      {
        var match = /^'([^']+)'|"([^"]+)"$/.exec(phrase);
        if (match)
          return match[1] || match[2] || "";
        else
          return phrase;
      });
  }

  function tokens(value)
  {
    return value.split(/[\s,]+/g).map(
      function (item)
      {
        return item.trim();
      }).filter(
        function (item)
        {
          return item;
        });
  }

  function with_keyword(keyword)
  {
    return function (term) { return term ? keyword + ":'" + term + "'" : ""; };
  }

  var summary = $("input[name='summary']").val().trim();
  var description = $("input[name='description']").val().trim();
  var repository = $("select[name='repository']").val();
  var branch = $("input[name='branch']").val().trim();
  var paths = tokens($("input[name='path']").val().trim());
  var users = tokens($("input[name='user']").val().trim());
  var owners = tokens($("input[name='owner']").val().trim());
  var reviewers = tokens($("input[name='reviewer']").val().trim());
  var state = $("select[name='state']").val();

  var terms = [];

  if (summary)
    terms.push.apply(terms, phrases(summary).map(with_keyword("summary")));

  if (description)
    terms.push.apply(terms, phrases(description).map(with_keyword("description")));

  if (repository && repository != "-")
    terms.push(with_keyword("repository")(repository));

  if (branch)
    terms.push(with_keyword("branch")(branch));

  terms.push.apply(terms, paths.map(with_keyword("path")));
  terms.push.apply(terms, users.map(with_keyword("user")));
  terms.push.apply(terms, owners.map(with_keyword("owner")));
  terms.push.apply(terms, reviewers.map(with_keyword("reviewer")));

  if (state && state != "-")
    terms.push(with_keyword("state")(state));

  quickSearch(terms.join(" "));
}

$(function ()
  {
    $("input").keypress(
      function (ev)
      {
        if (ev.keyCode == 13)
          search();
      });

    $("input[name='user'], input[name='owner'], input[name='reviewer']")
      .autocomplete({ source: AutoCompleteUsers(users) });
  });
