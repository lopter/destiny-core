{ buildPlatformPkgs, hostPlatformPkgs }:
  let
    mkAiosc = { pname, version, src, meta }:
      hostPlatformPkgs.python3Packages.buildPythonPackage rec {
        inherit pname version src meta;

        doCheck = false;
    };
  in
    mkAiosc rec {
      pname = "aiosc";
      version = "0.1.4";
      src = buildPlatformPkgs.python3Packages.fetchPypi {
        inherit pname version;
        sha256 = "74c021a255c6e521bab8e16225654090c9c2c95b87015fabba60b59bd9c700e6";
      };
      meta = with buildPlatformPkgs.lib; {
        homepage = "https://github.com/artfwo/aiosc";
        downloadPage = "https://github.com/artfwo/aiosc/releases";
        description = "Lightweight Open Sound Control implementation for Python using asyncio";
        longDescription = ''
          This is an experimental minimalistic Open Sound Control (OSC)
          communication module which uses asyncio for network operations and
          is compatible with the asyncio event loop.
        '';
        licenses = licenses.mit;
      };
    }
