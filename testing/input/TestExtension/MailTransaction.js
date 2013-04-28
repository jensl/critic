/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function test() {
  var data = JSON.parse(read());
  var transaction = new critic.MailTransaction;
  var message = null;

  try {
    data.mails.forEach(
      function (data) {
        transaction.add(data);
      });
    transaction.finish();
  } catch (error) {
    message = error.message;
  }

  writeln(200);
  writeln("Content-Type: text/json");
  writeln();
  writeln(JSON.stringify({ status: "ok", message: message }));
}
