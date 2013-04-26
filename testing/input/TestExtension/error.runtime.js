/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function test() {
  writeln(200);
  writeln("Content-Type: text/plain");
  writeln();
  writeln(new critic.User({ name: "nosuchuser" }).fullname);
}
