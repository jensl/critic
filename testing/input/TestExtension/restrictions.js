/* -*- mode: js; indent-tabs-mode: nil -*- */

"use strict";

function checkDatabaseConnection() {
  try {
    new PostgreSQL.Connection({ dbname: "critic",
                                user: "critic" });
    return "no error";
  } catch (error) {
    return error.message;
  }
}

function restrictions() {
  writeln(200);
  writeln("Content-Type: text/json");
  writeln();
  writeln("%r", { status: "ok",
                  database_connection: checkDatabaseConnection() });
}
