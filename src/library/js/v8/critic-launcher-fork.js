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

var data = JSON.parse(readln());

var critic = new Module();
critic.load(data.criticjs_path);
critic.close();

var server_socket = new IO.Socket("unix", "stream");

server_socket.bind(IO.SocketAddress.unix(data.address));
server_socket.listen(4);

writeln("listening");

function Child(socket)
{
  this.socket = socket;
  this.stdout = IO.File.pipe();
  this.stderr = IO.File.pipe();
  this.check = IO.File.pipe();
}

Child.prototype.start =
  function ()
  {
    this.socket.sendfd(this.stdout.input);
    this.stdout.input.close();

    this.socket.sendfd(this.stderr.input);
    this.stderr.input.close();

    this.process = new Process();
    this.process.start();

    if (this.process.isSelf)
    {
      this.check.input.close();

      File.dup2(this.socket, 0);
      this.socket.close();

      File.dup2(this.stdout.output, 1);
      this.stdout.output.close();

      File.dup2(this.stderr.output, 2);
      this.stderr.output.close();

      this.execute();

      this.check.output.close();

      Process.exit(0);
    }
    else
    {
      this.stdout.output.close();
      this.stderr.output.close();
      this.check.output.close();
    }
  };

Child.prototype.execute =
  function ()
  {
    try
    {
      var line = read().decode();
      var data = JSON.parse(line);
    }
    catch (e)
    {
      throw JSON.stringify(line);
    }

    critic.setup(data);

    try
    {
      var script = new Module();

      script.global.critic = critic;
      script.load(data.script_path);
      script.global[data.fn].apply(null, eval(data.argv));
    }
    finally
    {
      critic.shutdown();
    }
  };

Child.prototype.finish =
  function ()
  {
    if (this.process.wait(true))
    {
      var result = JSON.stringify({ exitStatus: this.process.exitStatus,
                                    terminationSignal: this.process.terminationSignal });

      this.socket.send(result + "\n");
      this.socket.close();

      return true;
    }
    else
      return false;
  };

var children = {};
var poll = new IO.Poll();

poll.register(server_socket);

while (true)
{
  if (poll.poll(1000))
  {
    poll.read.forEach(function (file) {
      if (file == server_socket)
      {
        var client_socket = server_socket.accept();

        writeln("%.3f: client connection opened", Date.now());

        var child = new Child(client_socket);

        child.start();
        children[child.process.pid] = child;

        poll.register(child.check.input);
      }
    });
  }

  for (var pid in children)
  {
    if (children[pid].finish())
    {
      poll.unregister(child.check.input);
      child.check.input.close();

      delete children[pid];

      writeln("%.3f: child process finished", Date.now());
    }
  }
}
