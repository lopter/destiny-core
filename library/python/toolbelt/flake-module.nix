{
  perSystem =
    { pkgs, inputs', ... }:
    {
      packages.toolbelt = pkgs.python3Packages.buildPythonApplication {
        pname = "clan-destiny";
        src = ./.;
        version = "1.0.0-rc.1";
        doCheck = false;

        build-system = with pkgs.python3Packages; [
          setuptools
          setuptools-scm
        ];

        dependencies = with pkgs.python3Packages; [
          click
          pexpect
          pyyaml
        ];

        propagatedBuildInputs = with pkgs; [
          cfssl
          sops

          inputs'.nixpkgs-unfree.legacyPackages.vault
        ];
      };
    };
}
