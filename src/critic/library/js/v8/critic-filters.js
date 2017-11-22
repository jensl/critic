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

function CriticFilters(data)
{
  var cli_input = {};

  if (data.review)
  {
    cli_input.review_id = data.review.id;
    if (data.added_review_filters)
    {
      cli_input.added_review_filters = [];
      for (var index = 0; index < data.added_review_filters.length; ++index)
      {
        var filter = data.added_review_filters[index];
        cli_input.added_review_filters.push([filter.uid, filter.path, filter.type, filter.delegate]);
      }
    }
    if (data.removed_review_filters)
    {
      cli_input.removed_review_filters = [];
      for (var index = 0; index < data.removed_review_filters.length; ++index)
      {
        var filter = data.removed_review_filters[index];
        cli_input.removed_review_filters.push([filter.uid, filter.path, filter.type, filter.delegate]);
      }
    }
  }
  else if (data.repository)
  {
    cli_input.repository_id = data.repository.id;
    cli_input.recursive = !!data.recursive;
    cli_input.file_ids = data.files.map(
      function (item)
      {
        if (!(item instanceof CriticFile))
          item = CriticFile.find(item);
        return item.id;
      });
  }

  if (data.user)
    cli_input.user_id = data.user.id;

  cli_input = JSON.stringify(cli_input) + "\n";

  var cli_args = [python_executable, "-m", "cli", "apply-filters"];
  var cli_process = new OS.Process(python_executable, { argv: cli_args,
                                                        environ: { PYTHONPATH: python_path }});
  var cli_output = cli_process.call(cli_input);

  this.files = JSON.parse(cli_output.trim());

  for (var file_id in this.files)
  {
    Object.freeze(this.files[file_id]);
    for (var user_id in this.files[file_id])
      Object.freeze(this.files[file_id][user_id]);
  }

  Object.freeze(this);
}

function getUserFileAssociation(filters, user_id, file_id)
{
  user_id = Number(user_id);
  file_id = Number(file_id);

  var data;

  if ((data = filters.files[file_id]) && (data = data[user_id]))
    return data[0];
  else
    return null;
}

CriticFilters.prototype.isReviewer = function (user_id, file_id)
  {
    return getUserFileAssociation(this, user_id, file_id) == "reviewer";
  };
CriticFilters.prototype.isWatcher = function (user_id, file_id)
  {
    return getUserFileAssociation(this, user_id, file_id) == "watcher";
  };
CriticFilters.prototype.isRelevant = function (user_id, file_id)
  {
    var association = getUserFileAssociation(this, user_id, file_id);
    return association == "reviewer" || association == "watcher";
  };

CriticFilters.prototype.listUsers = function (file_id)
  {
    var data = this.files[file_id];
    if (data)
      return data;
    else
      return {};
  };
