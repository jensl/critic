/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function evaluate() {
  var data = JSON.parse(read());

  writeln(200);
  writeln("Content-Type: text/json");
  writeln();

  try {
    var source = "(function () { " + data["source"] + " })";
    var fn = eval(source);
    writeln(JSON.stringify({ "status": "ok",
                             "result": fn() }));
  } catch (error) {
    writeln(JSON.stringify({ "status": "error",
                             "source": source,
                             "error": String(error) }));
  }
}
