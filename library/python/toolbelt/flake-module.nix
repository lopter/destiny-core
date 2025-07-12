{
  perSystem =
    { pkgs, inputs', ... }:
    let
      toolbelt = pkgs.python3Packages.buildPythonApplication {
        pname = "clan-destiny";
        src = ./.;
        version = "1.0.0-rc.1";
        doCheck = false;
        pyproject = true;

        build-system = with pkgs.python3Packages; [
          setuptools
          setuptools-scm
        ];

        dependencies = with pkgs.python3Packages; [
          click
          ovh
          pexpect
          pillow
          pyyaml
        ];

        propagatedBuildInputs = with pkgs; [
          cfssl

          (inputs'.nixpkgs-unfree.legacyPackages.vault.overrideAttrs (_prev: {
            doCheck = false;
          }))

          inputs'.clan-core.packages.clan-cli

          pass

          s3cmd
        ];
      };
    in
    {
      packages.toolbelt = toolbelt;
      devShells.toolbelt = pkgs.mkShell {
        propagatedBuildInputs = [
          pkgs.python3Packages.ipython
          toolbelt
        ];
      };
    };
}
