#!/usr/bin/env bash
set -euo pipefail

# The SDK tarball, not dotnet-install.sh: an install script fetched at build
# time runs as root at whatever content it has that day. The digest is
# hardcoded and was checked against the downloaded bytes, not just copied
# from the release metadata. Bump URL and digest together.
url="https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.401/dotnet-sdk-10.0.401-linux-x64.tar.gz"
sha512="51c8b999af9e8dd9998c9edc5944e19a90788862068acd38694e098889054ce8c23d4f0c5cccfa16bf187d044562359e5ee69a9f8ad0bbe913ba90311fbce25b"

curl --fail --silent --show-error --location "$url" -o dotnet.tar.gz
echo "${sha512}  dotnet.tar.gz" | sha512sum --check --strict
tar xzf dotnet.tar.gz
rm dotnet.tar.gz

# EF Core for the csharp-ef language (data-access exercises). Each package is
# pinned by the sha512 of its .nupkg, checked against the bytes NuGet restored
# for Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3 on net10.0; only the net10.0
# runtime assembly is kept. Bump a version and its digest together.
packages=(
    "Microsoft.EntityFrameworkCore 10.0.4 lib/net10.0/Microsoft.EntityFrameworkCore.dll 7ee1090f87758e988661315bc8f8358b75aac8241d4d1d8d100230002d20f16531c363c7ce6c2f4ae01b2783840513c601cc134c4abae175af38c3697b7b2671"
    "Microsoft.EntityFrameworkCore.Abstractions 10.0.4 lib/net10.0/Microsoft.EntityFrameworkCore.Abstractions.dll 1cb908eccd39244ccf8be1e96256a2f26df4df64e951be539b040e452e7a90c52dacc3745f111fe50ae8ad8128b6f3428070b1def0a84dec37c9076f1a3e0911"
    "Microsoft.EntityFrameworkCore.Relational 10.0.4 lib/net10.0/Microsoft.EntityFrameworkCore.Relational.dll 9516974d46e568eeb3f1d8c174c42101549aa30aa4cce9697430b00dba9a4641dfa0b3d884fc7cb37418145bdfb983f9fe44d4ba54be7b9a7779fb07f9ff0d09"
    "Microsoft.Extensions.Caching.Abstractions 10.0.4 lib/net10.0/Microsoft.Extensions.Caching.Abstractions.dll a0a063f6992fdb9e2b6d26615db779186844762d378d872311f12907b29ec2fc0b632edc439bcf517c725278f4e567e5baf9f56d602f0043300525c6864d35e4"
    "Microsoft.Extensions.Caching.Memory 10.0.4 lib/net10.0/Microsoft.Extensions.Caching.Memory.dll 66223e0db6e513cd010c5e46fb2395ffe6c9b7b20e4ddcac6c5eeb237f6f921a192f5a26a2db9019159cdbb750c087a976fed1f456a835f71e0b86cf39abdb6f"
    "Microsoft.Extensions.Configuration.Abstractions 10.0.4 lib/net10.0/Microsoft.Extensions.Configuration.Abstractions.dll eb770a4fdcaebd12e555fa047992f159621052a77f77b6c56df339a83dcbc43e3128452d92f30f8dd651481ec0f0b28b8116bace80fb8ec101e56bad6da9d1d1"
    "Microsoft.Extensions.DependencyInjection 10.0.4 lib/net10.0/Microsoft.Extensions.DependencyInjection.dll 5d0778a1c857f3b0269eb5b475db0b1100508832b0758a74ace2c18c16158da95e4e3786b7016fd0bfe33c6019d5df52d370b0d0fcb09699687184ccb43c16e3"
    "Microsoft.Extensions.DependencyInjection.Abstractions 10.0.4 lib/net10.0/Microsoft.Extensions.DependencyInjection.Abstractions.dll 124debe71cc246cf8e142e45cfac895fadd539059b6f0ec0d1aa4f1d1268ea7ed49be294ee22eefe2bd96269e8ebe1e297e42534098983f213b706e6f91c8d2f"
    "Microsoft.Extensions.Logging 10.0.4 lib/net10.0/Microsoft.Extensions.Logging.dll 2bfe5e6f7732874562e2a9d1a3c3b86ad5fdc5a701709e9848ea7d23cc3ca91cd5197d294a9f16ce681c92941f6c576922c45513aba821ba729056cae885fae0"
    "Microsoft.Extensions.Logging.Abstractions 10.0.4 lib/net10.0/Microsoft.Extensions.Logging.Abstractions.dll 60c5e7078ad6adb1c77875ac917660c4ba263ec248a4957748e50fc9cfcbf1fdeb08634e6313b547d8888d73acf256bceb95be3d652220fde54b241b336b0f50"
    "Microsoft.Extensions.Options 10.0.4 lib/net10.0/Microsoft.Extensions.Options.dll 1300b6e9a37d644236dc8c39c61a72c88cd9bdf8d208d2043f56142f6fea74cf26f3a7b747bbef9c6cc7c6de7b2b2eba91940d8dfa335fa25e8252858f329580"
    "Microsoft.Extensions.Primitives 10.0.4 lib/net10.0/Microsoft.Extensions.Primitives.dll e37827d1fd62aef6b8d2dbe2015a1745c819687bbdd10cca0dff91f05f3e25e25ac0d4d738a9eb9482a8b16f0ad9e4918211fc418759a026333640fa64f9d5a0"
    "Npgsql 10.0.3 lib/net10.0/Npgsql.dll f70658951eabd6e2c69c0c41b943ce0a681b4ba483b552b21a4674b4318f6811d86db7440c46a30f4544aeaf96fdd9f78077c9dd6bce75968d34dc9b9c50aea4"
    "Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3 lib/net10.0/Npgsql.EntityFrameworkCore.PostgreSQL.dll a68139df3b6f8b6301f4a502348c48d1a46edf80ce050c26e582ae0965402fc3549d77bf0348e216c393a757d1f79d130526a433b5915909ef0bebb8431977bd"
)
mkdir -p ef
for entry in "${packages[@]}"; do
    read -r id version dll sha512 <<< "$entry"
    lower=$(echo "$id" | tr '[:upper:]' '[:lower:]')
    curl --fail --silent --show-error --location --max-time 300 \
        "https://api.nuget.org/v3-flatcontainer/$lower/$version/$lower.$version.nupkg" -o pkg.nupkg
    echo "${sha512}  pkg.nupkg" | sha512sum --check --strict
    python3 -c "import sys, zipfile; open(sys.argv[3], 'wb').write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]))" \
        pkg.nupkg "$dll" "ef/$(basename "$dll")"
    rm pkg.nupkg
done
