{
  perSystem =
    { pkgs, ... }:
    let
      monfree = pkgs.python3Packages.buildPythonApplication {
        pname = "monfree";
        meta.mainProgram = "monfree";
        src = ./.;
        version = "1.0.0";
        doCheck = false;
        pyproject = true;

        build-system = with pkgs.python3Packages; [
          setuptools
        ];

        dependencies = with pkgs.python3Packages; [
          click
          prometheus-client
        ];

        propagatedBuildInputs = with pkgs; [
          mtr
        ];
      };
    in
    {
      packages.monfree = monfree;
      devShells.monfree = pkgs.mkShell {
        propagatedBuildInputs = [
          pkgs.python3Packages.ipython
          monfree.dependencies
        ];
      };
    };
}
