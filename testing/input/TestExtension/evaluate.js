/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function evaluate() {
  var data = JSON.parse(read());

  writeln(200);
  writeln("Content-Type: text/json");
  writeln();

  try {
    var fn = new Function(data["source"]);
    writeln(JSON.stringify({ "status": "ok",
                             "result": fn() }));
  } catch (error) {
    writeln(JSON.stringify({ "status": "failure",
                             "error": String(error) }));
  }
}
