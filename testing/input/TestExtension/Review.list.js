/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function test() {
  var passed = [];
  var failed = [];

  function correct(test, fn) {
    try {
      var reviews = fn();
      passed.push({ test: test, result: format("%d reviews", reviews.length) });
    } catch (error) {
      failed.push({ test: test, message: error.message });
    }
  }

  function incorrect(test, fn, expected) {
    try {
      fn();
      failed.push({ test: test, message: "no exception thrown" });
    } catch (error) {
      if (error.message != expected)
        failed.push({ test: test, message: format(
          "wrong error: expected=%r, actual=%r",
          expected, error.message) });
      else
        passed.push({ test: test, result: "call failed as expected" });
    }
  }

  /* For now we're only testing that the various calls produce correct database
     queries in so far that the database doesn't outright reject them. */

  correct("no filtering", function () {
    return critic.Review.list();
  });

  correct("filter by repository (instance)", function () {
    return critic.Review.list({ repository: new critic.Repository("critic") });
  });
  correct("filter by repository (id)", function () {
    return critic.Review.list({ repository: 1 });
  });
  correct("filter by repository (name)", function () {
    return critic.Review.list({ repository: "critic" });
  });

  correct("filter by state (open)", function () {
    return critic.Review.list({ state: "open" });
  });

  correct("filter by state (closed)", function () {
    return critic.Review.list({ state: "closed" });
  });

  correct("filter by state (dropped)", function () {
    return critic.Review.list({ state: "dropped" });
  });

  correct("filter by owner (instance)", function () {
    return critic.Review.list({ owner: new critic.User("alice") });
  });
  correct("filter by owner (id)", function () {
    return critic.Review.list({ owner: 1 });
  });
  correct("filter by owner (name)", function () {
    return critic.Review.list({ owner: "alice" });
  });

  /* Only check 'id' and 'name' variants from now on; the 'instance' variant
     is really just an alternative way to specify the id. */

  correct("filter by repository (id) and state", function () {
    return critic.Review.list({ repository: 1,
                                state: "open" });
  });
  correct("filter by repository (name) and state", function () {
    return critic.Review.list({ repository: "critic",
                                state: "open" });
  });

  correct("filter by repository (id) and owner (id)", function () {
    return critic.Review.list({ repository: 1,
                                owner: 1 });
  });
  correct("filter by repository (name) and owner (id)", function () {
    return critic.Review.list({ repository: "critic",
                                owner: 1 });
  });
  correct("filter by repository (id) and owner (name)", function () {
    return critic.Review.list({ repository: 1,
                                owner: "alice" });
  });
  correct("filter by repository (name) and owner (name)", function () {
    return critic.Review.list({ repository: "critic",
                                owner: "alice" });
  });

  correct("filter by state and owner (id)", function () {
    return critic.Review.list({ state: "open",
                                owner: 1 });
  });
  correct("filter by state and owner (name)", function () {
    return critic.Review.list({ state: "open",
                                owner: "alice" });
  });

  incorrect("filter by bogus state", function () {
    return critic.Review.list({ state: "bogus" });
  }, "invalid argument: data.state=\"bogus\" not valid");

  writeln(200);
  writeln("Content-Type: text/json");
  writeln();
  writeln(JSON.stringify({ status: "ok", passed: passed, failed: failed }));
}
