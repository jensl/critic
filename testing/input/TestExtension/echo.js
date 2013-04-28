/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function echo() {
  writeln(200);
  writeln("Content-Type: text/json");
  writeln();
  writeln(JSON.stringify({ "status": "ok",
                           "arguments": [].slice.call(arguments, 0, 3),
                           "headers": arguments[3],
                           "stdin": read() }));
}
