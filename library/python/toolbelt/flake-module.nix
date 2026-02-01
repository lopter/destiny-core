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
          pkgs.python3Packages.mypy

          toolbelt.nativeBuildInputs
          toolbelt.propagatedBuildInputs
        ];

        shellHook = ''
          export GIT_ROOT="$(git rev-parse --show-toplevel)"
          export PKG_ROOT="$GIT_ROOT/library/python/toolbelt"
          export PYTHONPATH="$PKG_ROOT''${PYTHONPATH:+:$PYTHONPATH:}"
          export PATH="$PKG_ROOT/bin":"$PATH"
        '';
      };
    };
}
