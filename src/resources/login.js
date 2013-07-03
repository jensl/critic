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

$(function ()
  {
    var username = $("input.username");
    var password = $("input.password");
    var submit = $("input.login");
    var form = $("form");

    submit.button();

    username.keypress(
      function (ev)
      {
        if (ev.keyCode == 13)
          password.focus();
      });

    password.keypress(
      function (ev)
      {
        if (ev.keyCode == 13)
          submit.click();
      });

    form.submit(
      function (ev)
      {
        var operation = new Operation({ action: "login",
                                        url: "validatelogin",
                                        data: { username: username.val(),
                                                password: password.val() }});
        var result = operation.execute();

        if (!result || result.message)
        {
          ev.preventDefault();

          if (result)
          {
            $("tr.status td").text(result.message);
            $("tr.status").removeClass("disabled");
          }
        }
      });
  });
