{
  perSystem = { pkgs, ... }:
  let
    backups = with pkgs.python3Packages; buildPythonPackage {
      pname = "multilab-backups";
      version = "0.0.1";
      src = ./.;

      build-system = [
        setuptools
        setuptools-scm
      ];

      dependencies = [
        click
      ];

      propagatedBuildInputs = with pkgs; [
        gzip
        restic
        rsync
        util-linux
      ];
    };
  in {
    packages.backups = backups;
    devShells.backups = pkgs.mkShell {
      propagatedBuildInputs = with pkgs.python3Packages; [
        backups
        ipython
      ];
    };
  };
}
