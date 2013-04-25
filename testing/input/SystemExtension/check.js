/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function check() {
  writeln(200);
  writeln("Content-Type: text/json");
  writeln();
  writeln(JSON.stringify({ "status": "ok" }));
}
