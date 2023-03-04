#!/bin/bash

shopt -s extglob

mkdir -p dist

contents="$(cat weechat_icat/util.py weechat_icat/!(util).py icat.py | \
  perl -0777 -pe 's/^( *from [^(\n]+\([^)]+\))/$1=~s|\s+| |gr/mge' | \
  grep -Ev '^from weechat_icat[. ]')"

(
  echo "# This is a compiled file."
  echo "# For the original source, see https://github.com/trygveaa/weechat-icat"
  echo
  echo "$contents" | grep '^from __future__' | sort -u
  echo "$contents" | grep -v '^from __future__' | grep -E '^(import|from)' | sort -u
  echo "$contents" | grep -Ev '^(import|from)' | sed 's/^\( \+\)\(import\|from\).*/\1pass/'
) > dist/icat.py
