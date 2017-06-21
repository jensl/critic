/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2015 the Critic contributors, Opera Software ASA

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

function checkIfFinished() {
  function handleResponse(data) {
    if (!data.pending_update)
      location.reload();
    else
      setTimeout(checkIfFinished, 2000);
  }

  JSON.fetch("reviews/" + review.id, { fields: "pending_update" }, handleResponse);
}

$(function () {
  setTimeout(checkIfFinished, 1000);
});
