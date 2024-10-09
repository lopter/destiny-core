{
  fetchFromGitHub,
  git,
  lib,
  libconfuse,
  liblo,
  libmonome,
  libuv,
  python3,
  stdenv,
  udev,
  wafHook,
}:
let
  mkSerialOSC = { pname, version, src, meta }:
    stdenv.mkDerivation {
      inherit pname version src meta;

      nativeBuildInputs = [
        wafHook
        python3
        git
      ];

      propagatedBuildInputs = [
        udev
      ];

      buildInputs = [
        libconfuse
        liblo
        libuv
        libmonome
      ];

      patches = [
        # Do not execute the program compiled to check if dependencies
        # were present, since it does not work when cross-compiling.
        ./serialosc_wscript_check_cc_execute_false.patch
      ];

      dontAddWafCrossFlags = true;

      wafConfigureFlags = [
        "--disable-zeroconf"
        "--enable-system-libuv"
      ];

      enableParallelBuilding = true;
    };
in
  mkSerialOSC rec {
    pname = "serialosc";
    version = "1.4.3";

    src = fetchFromGitHub {
      owner = "monome";
      repo = "serialosc";
      rev = "v${version}";
      sha256 = "rSBXPUoko0o1vCaZNXqzOoyXUWbvi4B5oFY649jHnAU=";
      # So that we pull the skeeto/optparse dependency from Github, this is
      # pretty impure because the submodule revision is not pinned. Maybe you
      # can fix that by downloading a tar.gz using a commit sha from github.
      # You'd have to figure out how to place optparse.h in the include path.
      #
      # Or maybe you could make a pull requests to serialosc to pin the
      # submodules.
      fetchSubmodules = true;
    };

    meta = with lib; {
      description = "An OSC server for monome devices";
      longDescription = ''
        serialosc is a daemon that waits for you to plug a monome in, then it
        spawns off a dedicated server process to route OSC messages to and
        from your monome.
      '';
      license = licenses.isc;
      homepage = "https://github.com/monome/serialosc";
    };
  }
