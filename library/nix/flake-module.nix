{ lib, ... }:
{
  flake.lib.attrsToEnvironmentString = (import ./attrsToEnvironmentString.nix) lib;
  flake.lib.dockerNssHelpers = (import ./dockerNssHelpers.nix) lib;
}
