/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function inject() {
  writeln("script %r", format("data:text/javascript,var injected=%r;",
                              [].slice.call(arguments)));
}

function showcommitShort() {
  writeln("script %r", format("data:text/javascript,var showcommitShort=%r;",
                              [].slice.call(arguments)));
}

function showcommitLong() {
  writeln("script %r", format("data:text/javascript,var showcommitLong=%r;",
                              [].slice.call(arguments)));
}
