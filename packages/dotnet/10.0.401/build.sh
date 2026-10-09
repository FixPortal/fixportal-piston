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

# Real xUnit/AwesomeAssertions/NSubstitute closure, restored only at image build.
# Digests are SHA512 of the downloaded nupkg bytes, not NuGet's contentHash.
tests_packages=(
    "awesomeassertions 9.6.0 de3a1e977ee79f7d2b6153f8fc03f6ef26e666c5dbc49c0c151cd270aca5ed527231a5718f305e5fd39d532725473787ab5409cfc69a71f32ad95c84f75026c3"
    "nsubstitute 6.2.0 c9ce3ca5006b71141d2e547480ee9ae93b0b1cddd997f9f8697ae221902a673cdebc71e89b988bbd32089094b5e9560a1b5889efb06ad10ec5cebe3f19fe72df"
    "xunit.v3 4.0.1 db45f6d50cce89d77cbbe0348179bc9099b16badb691a42f149edfe280913339d9d2af1d01b5cb4b24ea49da762d9738b90d2d817f32736856fe6c6701f63c49"
    "castle.core 5.1.1 378a149ebfaa12d00cb35bcaee8806803df7bc75980c9e0c67f36e3e057d6af2abaead24cd8274a9595c7ac74cb9597c9d6913b1125b86e6b156a66f7a1ac2fa"
    "microsoft.applicationinsights 2.23.0 dd497bfad0c65e54a4f78d2a1644f3d0854d4cd01dd83ba506f8d5d53635e28152c7c13210dd5dd3985780aab146a7620de3ebaead8ef12c6f87088676c2157f"
    "microsoft.bcl.asyncinterfaces 6.0.0 221a05a0c910f7a87b620d8f3831ed392b4eb95d112bee274d35f27009ad2a26445de9d7cd235fe6fb4a03f2550874bda3be3dddd96edaf9c0852a9c23d7b099"
    "microsoft.testing.extensions.telemetry 2.4.0 493ddac3032b82f378e6fecb4fd07163746ad369235c270be0e67a756d3a3d9bbc0d1d1f25f1f89cae8f537c95e0f9c688f27ad87d694a6b26f0544ceb4f0c4a"
    "microsoft.testing.extensions.trxreport.abstractions 2.4.0 dc636209efc00f142d85d7154fa3a906551aa8b75c510b15d765483ef56146ad86862698b962c8eb0c09f8f1fe3382b472bdbb792c3689a9b3a5ce69d969d5c4"
    "microsoft.testing.platform 2.4.0 36103b3aed647ea427a35868bb8321e4257286f7449f8777b63f040ea8183291b223b372090eda957537f089cd9d87e560b889758d40ae6f8f413f5b571f690e"
    "microsoft.testing.platform.msbuild 2.4.0 08d93413536bf47f1aa4bdeb69ea1735852b700b3ffe26f323ff6b6fb36a82835d74f475f169fa726fe657937c2687926cbaf32c07ebd6d00e1fd5f00d1820a8"
    "microsoft.win32.registry 5.0.0 471e66567ce59cc86475aece7815d05261264ce114e0c1688ba2551dd51494901fa72dd7a8f74f8e8f0f3dba74af8595f177552f3c06abb4bfce76692197076e"
    "system.diagnostics.eventlog 6.0.0 40103d5b7cb2b41c7cafca629c112c5526bb773d11367ca62918d8864fba8dac2b48151f37671bcf50499d8f8b268489ee1cade2fb8947cc06e205a1fac6784c"
    "system.security.accesscontrol 6.0.1 e1beba70b45f8cc5ae06fdecf365f0bb5b58b9af6d7c79accfef15b5a7c7bbef65e10cf9f299418eb413aac86ffefaa0eab9d91650ce77cc398d390f0597ed42"
    "xunit.analyzers 2.1.0 07b2897501b4a4c53435cf4c851b72e1b6a080da653ab90ea4f70033795617209dd10dd604070d890c6d86848cd806514cc9d57c7d18b33b39bb28e9b4374c38"
    "xunit.v3.assert 4.0.1 1a83aac30ef23406a5bbda19756ccd56a348eb18b573ec837b5ab812ba7b4c6ce045b6c93a31d8404c5dc22f11c3f9ef1bd1b2635be37d193a6a96f4196cf705"
    "xunit.v3.common 4.0.1 880a8bbb813ad4d9f0f0d134b3f1e1720d451834295527f55e0e223b41225a724cd686af72d0b655b466e109e499ce93247c64a77c720357a0faae842d45455e"
    "xunit.v3.core.mtp-v2 4.0.1 98e0b1cd39d9002ed6c385592f27e503834bfbeb079b5761eeb4363ab0205432cdedd2eea5c630c733ab12da624b02da7a8f3aed07f155b0cabdbd8c303b04a2"
    "xunit.v3.extensibility.core 4.0.1 52519af4388a9fd8def98bab5314ce6f2dc91efff8e3e2b4576c052ae56a69ae1b1f81b8fad3aeb4c691e8f902185b2be8dfaac3320932567a523655553e524a"
    "xunit.v3.mtp-v2 4.0.1 ba20c62e9a4a0748519c2369d1e131902f3e9759ccb5bb47146154a38c39943f9452e753daed387f3566b66a8e4adb9b575357f422828bb529ce204f3cb6529e"
    "xunit.v3.runner.common 4.0.1 6752469c0ab994e666a447cdb83d86cd83d64209e4d4e9225642c75f6d3aad3291f9ac69d67ae091df0087a5f3794860c945a029110b24675043182d9b48e6f3"
    "xunit.v3.runner.inproc.console 4.0.1 281e334912a140ab2d918c10b271931fd64d4ce96caa2fe0a8ba900b5d05a577e4f252e2a998346050e27abc093e1ef2ae1322af21385b4e9adc3bb033fe9ed6"
)
mkdir -p tests-feed
for entry in "${tests_packages[@]}"; do
    read -r id version sha512 <<< "$entry"
    curl --fail --silent --show-error --location --max-time 300 \
        "https://api.nuget.org/v3-flatcontainer/${id}/${version}/${id}.${version}.nupkg" \
        -o "tests-feed/${id}.${version}.nupkg"
    echo "${sha512}  tests-feed/${id}.${version}.nupkg" | sha512sum --check --strict
done
cat > tests-package/NuGet.Config <<EOF
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="verified" value="${PWD}/tests-feed" />
  </packageSources>
</configuration>
EOF
./dotnet restore tests-package/TestsPackage.csproj --locked-mode --force \
    --configfile tests-package/NuGet.Config --packages "$PWD/tests-cache"
./dotnet publish tests-package/TestsPackage.csproj -c Release -o tests --no-restore
mkdir -p tests-bootstrap
# Reproduce the package's assembly registrations in direct-csc submissions.
cp tests-cache/xunit.v3.core.mtp-v2/4.0.1/_content/DefaultResultWriters.cs tests-bootstrap/
cp tests-cache/xunit.v3.core.mtp-v2/4.0.1/_content/DefaultRunnerReporters.cs tests-bootstrap/
rm tests/app tests/app.dll tests/app.pdb
rm -rf tests-feed tests-cache tests-package/NuGet.Config tests-package/obj tests-package/bin
