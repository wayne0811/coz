#!/bin/sh
set -e
git submodule init
git submodule update

DEST="./coz"
mkdir -pv $DEST
cp -v jsonrpyc/jsonrpyc.py $DEST
cp -rv py-ipfs-api/ipfsapi $DEST
cp -rv pyaes-git/pyaes $DEST
cp -rv mvc $DEST
packages="jsonrpyc.py ipfsapi pyaes mvc"
(cd $DEST && python -m compileall . && 7z a -mx=0 packages.zip .)
mv -v $DEST/packages.zip .
rm -r $DEST
mvdir -pv $DEST
mv -v packages.zip $DEST

cp -rv node $DEST
(cd $DEST/node && npm install)

cp -v __main__.py $DEST

out=coz.zip
7z a coz.zip $DEST
echo Done
