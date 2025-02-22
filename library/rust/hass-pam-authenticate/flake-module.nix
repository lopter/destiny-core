{ lib, ... }:
{
  perSystem =
    { pkgs, setupCraneLib, setupRustToolchain, ... }:
    let
      toolchainCfg = {
        nightly = false;
        withWasm32 = false;
      };
      rustToolchain = setupRustToolchain toolchainCfg;
      craneLib = setupCraneLib toolchainCfg;
      buildInputs = with pkgs; [
        pam
        rustPlatform.bindgenHook
      ];
    in
    {
      devenv.shells.hass-pam-authenticate = {
        name = "hass-pam-authenticate";

        packages = rustToolchain ++ buildInputs;
      };

      packages.hass-pam-authenticate = craneLib.buildPackage {
        inherit buildInputs;

        pname = "hass-pam-authenticate";
        version = "0.1.0";

        src = lib.cleanSourceWith {
          src = ./.;
          filter = path: type: craneLib.filterCargoSources path type;
        };

        strictDeps = true;
      };
    };
}
