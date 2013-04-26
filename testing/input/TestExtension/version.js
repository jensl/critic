/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function version() {
  writeln(200);
  writeln("Content-Type: text/plain");
  writeln();
  write(IO.File.read("version.txt"));
}
