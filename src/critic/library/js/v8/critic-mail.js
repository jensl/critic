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

function sendMail(filename)
{
  IO.File.rename(filename, /^(.*)\.pending$/.exec(filename)[1]);
}

function CriticMailTransaction()
{
  this.mails = [];
}

CriticMailTransaction.prototype.add = function (data)
  {
    if (!("to" in data) && !("review" in data))
      throw CriticError("invalid argument; at least one of data.to or data.review must be specified");
    if (!("subject" in data))
      throw CriticError("invalid argument; data.subject is required");
    if (!("body" in data))
      throw CriticError("invalid argument; data.body is required");

    var mail = { subject: String(data.subject),
                 body: String(data.body) };

    if ("to" in data)
    {
      mail.recipients = [];
      if (typeof data.to == "object" && "length" in data.to)
      {
        for (var index = 0; index < data.to.length; ++index)
          mail.recipients.push((new CriticUser(data.to[index])).id);
      }
      else
        mail.recipients.push((new CriticUser(data.to)).id);
    }

    if ("from" in data)
      mail.sender = (new CriticUser(data.from)).id;
    else
      mail.sender = global.user.id;

    if ("review" in data)
      mail.review_id = (new CriticReview(data.review)).id;

    if ("headers" in data)
    {
      mail.headers = {};
      for (var name in data.headers)
        mail.headers[name] = String(data.headers[name]);
    }

    this.mails.push(mail);
  };

CriticMailTransaction.prototype.finish = function ()
  {
    var argv = [python_executable, "-m", "cli", "generate-custom-mails"];
    var stdin_data = format("%r\n", this.mails);

    var process = new OS.Process(python_executable,
                                 { argv: argv,
                                   environ: { PYTHONPATH: python_path }});

/*
    process.stdout = new IO.MemoryFile;
    process.stderr = new IO.MemoryFile;
    process.start();
    process.wait();

    if (process.exitStatus !== 0)
      throw CriticError(process.stderr.value.decode());

    var stdout_data = process.stdout.value.decode().trim();
*/

    var stdout_data = process.call(stdin_data).trim();
    var response = JSON.parse(stdout_data);

    if (typeof response == "string")
      throw CriticError(response);

    response.forEach(sendMail);

    var maildelivery_pid =
      parseInt(IO.File.read(maildelivery_pid_path).decode().trim());

    OS.Process.kill(maildelivery_pid, 1);
  };
