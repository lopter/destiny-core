{
  perSystem =
    { pkgs, ... }:
    let
      hass-pam-authenticate = pkgs.python3Packages.buildPythonApplication {
        pname = "hass-pam-authenticate";
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
          python-pam
        ];

        propagatedBuildInputs = with pkgs; [
          coreutils
        ];
      };
    in
    {
      packages.hass-pam-authenticate = hass-pam-authenticate;
      devShells.hass-pam-authenticate = pkgs.mkShell {
        propagatedBuildInputs = [
          pkgs.python3Packages.ipython
          hass-pam-authenticate
        ];
      };
    };
}
