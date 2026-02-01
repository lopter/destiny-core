{
  perSystem =
    { pkgs, inputs', ... }:
    let
      toolbelt = pkgs.python3Packages.buildPythonApplication {
        pname = "clan-destiny";
        src = ./.;
        version = "1.0.0-rc.1";
        pyproject = true;

        build-system = with pkgs.python3Packages; [
          setuptools
        ];

        dependencies = with pkgs.python3Packages; [
          boto3
          click
          ovh
          pexpect
          pillow
          pyyaml
        ];

        nativeCheckInputs = [
          pkgs.python3Packages.boto3-stubs
          pkgs.python3Packages.types-pyyaml
        ];

        propagatedBuildInputs = with pkgs; [
          cfssl

          (inputs'.nixpkgs-unfree.legacyPackages.vault.overrideAttrs (_prev: {
            doCheck = false;
          }))

          inputs'.clan-core.packages.clan-cli

          pass
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
