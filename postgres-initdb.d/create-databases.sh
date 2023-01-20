#!/bin/bash

set -ex
set -x

if [ -n "$POSTGRES_DB_LIST" ]; then
	for db in $POSTGRES_DB_LIST; do
        echo "Create database $db"
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --command "CREATE DATABASE $db OWNER $POSTGRES_USER"
	done
fi
