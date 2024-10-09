let
  fakeSunPkgs = final: prev: {
    redshift = prev.callPackage ./redshift.nix {};
  };
  # It would be nice if we could inject aiosc and pymonome into the python
  # package set from here as well, but I couldn't figure out how to
  # properly setup a Python overlay using packageOverrides for that.
  monolightPkgs = final: prev: {
    lightsd = prev.callPackage ./lightsd.nix {};
    libmonome = prev.callPackage ./libmonome.nix {};
    serialosc = final.callPackage ./serialosc.nix {};
  };
in [ fakeSunPkgs monolightPkgs ]
