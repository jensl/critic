/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2014 the Critic contributors, Opera Software ASA

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

function createUser() {
  var data = {
    username: $("#newusername").val().trim(),
    fullname: $("#fullname").val().trim(),
    email: $("#email").val().trim()
  };

  if (external) {
    data.external = external;
  } else {
    var password1 = $("#password1").val();
    var password2 = $("#password2").val();

    if (password1 != password2) {
      showMessage("Invalid input",
                  "Password mismatch!",
                  "The password must be input twice.");
      return;
    }

    data["password"] = password1;
  }

  var operation = new Operation({
    action: "create user",
    url: "registeruser",
    data: data
  });

  var result = operation.execute();
  if (result) {
    if (result.message) {
      $(".status").removeClass("disabled").find(".message").html(result.message);
      if (result.focus)
        $(result.focus).select().focus();
    } else if (typeof target != "undefined") {
      location.replace(target);
    } else {
      location.replace("/");
    }
  }
}

$(function () {
  if ($(".status .message").text().trim())
    $(".status").removeClass("disabled");

  $(".create").click(createUser);
});
