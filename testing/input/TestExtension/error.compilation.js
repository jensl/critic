/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

/* Strict mode disallows duplicated parameter names. */
function wrong(x, x) {
}

function irrelevant() {
  writeln(200);
  writeln("Content-Type: text/plain");
  writeln();
}
