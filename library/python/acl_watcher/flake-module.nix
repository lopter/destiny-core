{
  perSystem =
    { pkgs, ... }:
    {
      packages.acl-watcher =
        with pkgs.python3Packages;
        buildPythonApplication {
          pname = "acl-watcher";
          src = ./.;
          version = "1.0.0-rc.1";
          doCheck = false;

          build-system = [
            setuptools
            setuptools-scm
          ];

          dependencies = [
            click
            pywatchman
          ];

          propagatedBuildInputs = with pkgs; [
            acl
          ];
        };
    };
}
