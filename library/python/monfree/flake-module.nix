{
  perSystem =
    { pkgs, ... }:
    let
      pythonPkgs = pkgs.python314Packages;
      monfree = pythonPkgs.buildPythonApplication {
        pname = "monfree";
        meta.mainProgram = "monfree";
        src = ./.;
        version = "1.0.0";
        doCheck = false;
        pyproject = true;

        build-system = with pythonPkgs; [
          setuptools
        ];

        dependencies = with pythonPkgs; [
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
          pythonPkgs.ipython
          monfree.dependencies
        ];
      };
    };
}
