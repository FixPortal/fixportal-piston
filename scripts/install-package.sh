#!/usr/bin/env bash
# Install a package source dir the way ppman installs a downloaded tarball:
# build it in place, then write pkg-info.json, the cached .env, and the
# installed marker the API looks for at startup.
# Usage: install-package <lang> <version>   (source staged at /stage/<lang>/<version>)
set -euo pipefail
dest=/piston/packages/$1/$2
rm -rf "$dest"
mkdir -p "$dest"
cp -r "/stage/$1/$2/." "$dest/"
cd "$dest"
chmod +x build.sh run environment
if [ -f compile ]; then chmod +x compile; fi
./build.sh
# Upstream's Makefile stamps build_platform with jq; the API warns at startup
# when it does not match the image's own platform.
sed '1s/^{/{"build_platform": "docker-debian",/' metadata.json > pkg-info.json
env -i bash -c "cd $dest; source environment; env" | grep -vE '^(PWD|OLDPWD|_|SHLVL)=' > .env
touch .ppman-installed
chown -R piston:piston "$dest"
echo "installed $1 $2"
