{ fetchFromGitHub, lib, liblo, python3, stdenv, wafHook }:
let
  mkLibMonome = { pname, version, src, meta }:
    stdenv.mkDerivation {
      inherit pname version src meta;

      nativeBuildInputs = [
        wafHook
        python3
      ];

      buildInputs = [
        liblo
      ];

      patches = [
        # Do not execute the program compiled to check if udev or liblo
        # were present, since it does not work when cross-compiling.
        ./libmonome_wscript_check_cc_execute_false.patch
      ];

      dontAddWafCrossFlags = true;

      wafConfigureFlags = [
        "--disable-udev"
      ];

      enableParallelBuilding = true;
    };
in
  mkLibMonome rec {
    pname = "libmonome";
    version = "1.4.5";

    src = fetchFromGitHub {
      owner = "monome";
      repo = "libmonome";
      rev = "v${version}";
      sha256 = "Kj5/+6gnqKfeClNh3gAcghJ6q9KpygbN32ulSf2Q7iw=";
    };

    meta = with lib; {
      description = "A library for easy interaction with monome devices";
      license = licenses.isc;
      homepage = "https://github.com/monome/libmonome";
    };
  }
