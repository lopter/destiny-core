{
  perSystem =
    { pkgs, ... }:
    let
      backups =
        with pkgs.python3Packages;
        buildPythonPackage {
          pname = "backups";
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
    in
    {
      apps.backups-dump.type = "app";
      apps.backups-dump.program = "${backups}/bin/clan-destiny-backups-dump";
      apps.backups-restore.type = "app";
      apps.backups-restore.program = "${backups}/bin/clan-destiny-backups-restore";
      packages.backups = backups;
      devShells.backups = pkgs.mkShell {
        propagatedBuildInputs = with pkgs.python3Packages; [
          backups
          ipython
        ];
      };
    };
}
