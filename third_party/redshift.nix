{
  autoconf,
  automake,
  fetchFromGitHub,
  gettext,
  intltool,
  lib,
  libtool,
  pkg-config,
  stdenv,
}:
let
  # myStdenv = hostPlatformPkgs.stdenvAdapters.keepDebugInfo hostPlatformPkgs.stdenv;
  mkRedshift = { pname, version, src, meta }:
    stdenv.mkDerivation {
      inherit pname version src meta;

      nativeBuildInputs = [
        autoconf
        automake
        gettext
        intltool
        libtool
        pkg-config
      ];

      configureFlags = [
        "--enable-randr=no"
        "--enable-geoclue2=no"
        "--enable-drm=no"
        "--enable-quartz=no"
        "--enable-corelocation=no"
        "--enable-gui=no"
        "--enable-vidmode=no"
        "--enable-ubuntu=no"
        "--enable-apparmor=no"
      ];

      preConfigure = "./bootstrap";

      enableParallelBuilding = true;
    };
in
  mkRedshift rec {
    pname = "redshift";
    version = "1.12";

    src = fetchFromGitHub {
      owner = "jonls";
      repo = "redshift";
      rev = "v${version}";
      sha256 = "12cb4gaqkybp4bkkns8pam378izr2mwhr2iy04wkprs2v92j7bz6";
    };

    meta = with lib; {
      description = "Screen color temperature manager";
      longDescription = ''
        Redshift adjusts the color temperature according to the position
        of the sun. A different color temperature is set during night and
        daytime. During twilight and early morning, the color temperature
        transitions smoothly from night to daytime temperature to allow
        your eyes to slowly adapt. At night the color temperature should
        be set to match the lamps in your room.
      '';
      license = licenses.gpl3Plus;
      homepage = "http://jonls.dk/redshift";
      platforms = platforms.unix;
    };
  }
