{ lib, ... }:
{
  flake.lib.attrsToEnvironmentString = (import ./attrsToEnvironmentString.nix) lib;
  flake.lib.dockerNssHelpers = (import ./dockerNssHelpers.nix) lib;
  flake.lib.escapeSystemdDirectiveArg = (import ./escapeSystemdDirectiveArg.nix) lib;
}
