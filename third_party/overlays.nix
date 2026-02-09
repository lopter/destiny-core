let
  fakeSunPkgs = _final: prev: {
    redshift = prev.callPackage ./redshift.nix { };
  };
  # It would be nice if we could inject aiosc and pymonome into the python
  # package set from here as well, but I couldn't figure out how to
  # properly setup a Python overlay using packageOverrides for that.
  monolightPkgs = final: prev: {
    lightsd = prev.callPackage ./lightsd.nix { };
    libmonome = prev.callPackage ./libmonome.nix { };
    serialosc = final.callPackage ./serialosc.nix { };
  };
  python314Compat = final: prev: {
    # Scope it to python 3.14 only since sphinx is a dependency for a lot of
    # non-python stuff and we would end-up rebuilding a LOT of packages.
    python314 = prev.python314.override {
      packageOverrides = _python-final: python-prev: {
        types-hvac = final.python314Packages.callPackage ./pypi/types-hvac.nix { };
        astor = python-prev.astor.overridePythonAttrs (_oldattrs: {
          patches = [
            (builtins.fetchurl {
              url = "https://github.com/mgorny/astor/commit/d0b5563cc1e263f08df9312d89a7691167448f4d.patch";
              name = "astor-python314-compat.patch";
              sha256 = "0rgibibyzp9c6jbxvmrsplx0cr40nx0m470rwsp7y2s87zhxwgyp";
            })
          ];
        });
        traitlets = python-prev.traitlets.overridePythonAttrs (_oldattrs: {
          patches = [
            (builtins.fetchurl {
              url = "https://github.com/ipython/traitlets/commit/d542080d1be24c95b05169b3af1754e25978c440.patch";
              name = "traitlets-python314-compat.patch";
              sha256 = "1md8mis4nsb19cvbb4gvsapjx7cs1ad5jr1b6ynbxahay3z7g064";
            })
          ];
        });
        jedi = python-prev.jedi.overridePythonAttrs (_oldattrs: {
          # https://github.com/davidhalter/jedi/issues/2064
          doCheck = false;
        });
        pyhamcrest = python-prev.pyhamcrest.overridePythonAttrs (_oldattrs: {
          # https://github.com/hamcrest/PyHamcrest/pull/270
          patches = [
            (builtins.fetchurl {
              url = "https://github.com/hamcrest/PyHamcrest/commit/bfe0ff68d1b1c9601a7a4bf4b6ce8aded1ea0c9e.patch";
              name = "pyhamcrest-python314-compat-1.patch";
              sha256 = "0656lyr2kakj2v1bxhspgp5fvhv9fdg69wzlzc8m0fw5nfb9iym9";
            })
            (builtins.fetchurl {
              url = "https://github.com/hamcrest/PyHamcrest/commit/5f5ca0424cc9315504e8445cae2076e55764859b.patch";
              name = "pyhamcrest-python314-compat-2.patch";
              sha256 = "07pb6lljwzddz0z80z8wdpyx7gl3k8nncsgf2zm2n6ip0inq1hvh";
            })
          ];
        });
        html5lib = python-prev.html5lib.overridePythonAttrs (_oldattrs: {
          patches = [
            (builtins.fetchurl {
              url = "https://github.com/html5lib/html5lib-python/commit/b90dafff1bf342d34d539098013d0b9f318c7641.patch";
              name = "html5lib-python314-compat.patch";
              sha256 = "1dr82q56bm3m61md51prn19hfbsypfmc2gf46qjzz4i55kp6ac19";
            })
          ];
        });
        sphinx = python-prev.sphinx.overridePythonAttrs (_oldattrs: {
          # they don't pass and upgrading sphinx causes other issues:
          doCheck = false;
        });
        distutils = python-prev.distutils.overridePythonAttrs (_oldattrs: {
          doCheck = false;
        });
        anyio = python-prev.anyio.overridePythonAttrs (_oldattrs: rec {
          version = "4.12.0";
          src = final.fetchFromGitHub {
            owner = "agronholm";
            repo = "anyio";
            tag = version;
            hash = "sha256-zFVvAK06HG40numRihLHBMKCI3d1wQvmEKk+EaBFVVU=";
          };
          doCheck = false;
        });
      };
    };
  };
  typesHvac = final: prev:
    let
      packageOverrides = _py-final: _py-prev: {
        types-hvac = prev.python3Packages.callPackage ./pypi/types-hvac.nix { };
      };
    in
    {
      python3 = prev.python3.override { inherit packageOverrides; };
      python3Packages = final.python3.pkgs;
    };
in
[
  fakeSunPkgs
  monolightPkgs
  python314Compat
  typesHvac
]
