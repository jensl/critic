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

/* -*- Mode: js; js-indent-level: 2; indent-tabs-mode: nil -*- */

$(document).ready(
  function ()
  {
    $("button.add").click(
      function (ev)
      {
        var name = $("input[name='name']").val();
        var path = $("input[name='path']").val();
        var remote = $("input[name='remote']").val();
        var branch = $("input[name='branch']").val();

        if (!/^[.a-z_0-9-]+$/.test(name))
        {
          alert("Invalid 'Short name'; please use only lower-case letters and digits.");
          return;
        }

        if (!/^(?:[.a-z_0-9-]+\/)?[.a-z_0-9-]+$/.test(path))
        {
          alert("Invalid 'path'; must consist only of lower-case letters and digits.");
          return;
        }

        var data = { name: name,
                     path: path };

        if (remote.trim())
          data.remote = { url: remote,
                          branch: branch };

        var operation = new Operation({ action: "add repository",
                                        url: "addrepository",
                                        data: data });

	if (operation.execute())
	  location.href = "/repositories#" + name;
      });
  });
