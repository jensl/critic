/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2014 Jens Lindström, Opera Software ASA

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

function executeCLI(commands)
{
  var argv = [python_executable, "-m", "cli"], stdin = "";

  commands.forEach(
    function (command)
    {
      argv.push(command.name);
      stdin += format("%r\n", command.data);
    });

  var process = new OS.Process(python_executable,
                               { argv: argv,
                                 environ: { PYTHONPATH: python_path }});

  return process.call(stdin).trim().split("\n");
}
