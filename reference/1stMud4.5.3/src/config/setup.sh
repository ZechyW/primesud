#!/bin/sh

fail()
{
	echo ""
	echo "ERROR: $@"
	echo ""
	echo "Using default Makefile and config file.  Some options may not suite your system!"
	cp -f ./Makefile.fail ../Makefile
	cp -f ./config.h.fail ../h/config.h
	echo > ../.depend
	exit 1
}

error()
{
	echo ""
	echo "ERROR: $@"
	exit 1
}

conf()
{
	./configure $@ || error "./configure script failed!!"

	echo ""
	echo "Setup complete."
	echo ""
}

autoheader || fail "autoheader failed.  You need to upgrade autoconf."
autoconf || fail "autoconf failed.  You need to upgrade autoconf."

conf $1 $2 $3 $4 $5 $6 $7 $8 $9

exit

