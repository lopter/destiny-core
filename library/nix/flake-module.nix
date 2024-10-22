{ lib, ... }:
{
  flake.lib.attrsToEnvironmentString = (import ./attrsToEnvironmentString.nix) lib;
}
