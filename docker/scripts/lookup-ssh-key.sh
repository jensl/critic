#!/bin/sh

/var/lib/critic/bin/criticctl lookup-ssh-key \
	--expected-user=$1 \
	--authenticating-user=$2 \
	--key-type=$3 \
	--key=$4
