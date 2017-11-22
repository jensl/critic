#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<EOF
 CREATE USER critic;
 CREATE DATABASE critic;
 GRANT ALL PRIVILEGES ON DATABASE critic TO critic;
EOF
