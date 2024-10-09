{ buildPlatformPkgs, python3Packages }:
  let
    mkOFXStatement = { pname, version, src, meta }:
      with python3Packages; buildPythonPackage rec {
        inherit pname version src meta;

        propagatedBuildInputs = [ appdirs setuptools ];

        doCheck = false;
      };
  in
  mkOFXStatement rec {
    pname = "ofxstatement";
    version = "0.6.1";
    # Technically not from PyPi but eh.
    src = buildPlatformPkgs.fetchFromGitHub {
      owner = "lopter";
      repo = "ofxstatement";
      rev = "lopter/fix-date-user-type";
      sha256 = "sha256-0ghrvBrRIiZUL9wnTIcDguDW93ACDguP+JkC+ixXF5w=";
    };
    meta = with buildPlatformPkgs.lib; {
      homepage = "https://github.com/lopter/ofxstatement/tree/lopter/fix-date-user-type";
      description = "An old fork of ofxstatement that works for me";
      licenses = licenses.gpl3;
    };
  }
