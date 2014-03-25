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

try { var line = readln(); var data = JSON.parse(line); } catch (e) { writeln(JSON.stringify(line)); throw e; }

var critic = new Module();
critic.load(data.criticjs_path);
critic.setup(data);
critic.close();

function run()
{
  try
  {
    var script = new Module({ PostgreSQL: false });
    script.global.critic = critic;
    script.eval("var Encodings = { decode: function (bytes) { return typeof bytes == 'object' ? bytes.decode.apply(bytes, [].slice.call(arguments, 1)) : bytes; } };");

    try
    {
      script.load(data.script_path);
    }
    catch (error)
    {
      IO.File.stderr.write(format("Failed to load '%s':\n  %s",
                                  data.script_path, error));
      return 1;
    }

    try
    {
      script.global[data.fn].apply(null, eval(data.argv));
    }
    catch (error)
    {
      IO.File.stderr.write(format("Failed to call '%s::%s()':\n  %s\n    %s",
                                  data.script_path, data.fn,
                                  error,
                                  error.stack.replace(/\n/g, "\n    ")));
      return 1;
    }

    return 0;
  }
  finally
  {
    critic.shutdown();
  }
}

OS.Process.exit(run());
