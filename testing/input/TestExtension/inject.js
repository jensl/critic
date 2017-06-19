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

function injectCustom(path, query) {
  if (query && query.params.expr) {
    writeln("script %r", format("data:text/javascript,var injectedCustom=%r;",
                                eval(query.params.expr)));
  }
}
