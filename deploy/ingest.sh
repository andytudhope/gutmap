#!/bin/sh
set -eu
set -a
. /etc/gut-atlas.env
set +a
cd /opt/gut-atlas
exec /usr/bin/python3 -m hub.ingest "$@"
