{ buildPlatformPkgs, hostPlatformPkgs, aiosc }:
  let
    mkPymonome = { pname, version, src, meta }:
      hostPlatformPkgs.python3Packages.buildPythonPackage rec {
        inherit pname version src meta;

        propagatedBuildInputs = [ aiosc ];

        doCheck = false;
      };
  in
    mkPymonome rec {
      pname = "pymonome";
      version = "0.10.1";
#     src = buildPlatformPkgs.python3Packages.fetchPypi {
#       inherit pname version;
#       sha256 = "3d67fad363bf85f15c33b73d6b55333ac63391130454c5110685574de3e8cfe0";
#     };
      src = buildPlatformPkgs.fetchFromGitHub {
        owner = "lopter";
        repo = "pymonome";
        rev = "fbcbfc69041996407c0cb081e3f21866afe6bee8";
        sha256 = "c0DKnIJSvLdjsVZeF7Y5nYG0QR3lHaL7Fd96szu5YkY=";
      };
      meta = with buildPlatformPkgs.lib; {
        homepage = "https://github.com/artfwo/pymonome";
        downloadPage = "https://github.com/artfwo/pymonome/releases";
        description = "A monome serialosc client in Python";
        longDescription = "A monome application library for Python.";
        licenses = licenses.mit;
      };
    }
