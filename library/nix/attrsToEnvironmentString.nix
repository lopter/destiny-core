lib:
{
  varPrefix ? "",
  attrs,
}:
let
  # Turns a set like { package = { module = { var1 = "val1"; }; }; }
  # Into [ "PACKAGE_MODULE_VAR1=val1" ]
  mapAttrsRecursiveToList =
    set:
    let
      makePair =
        lineage: key:
        let
          path = lineage ++ [ key ];
          value = lib.attrsets.attrByPath path null set;
          name = lib.strings.toUpper (builtins.concatStringsSep "_" path);
        in
        if builtins.isAttrs value then
          map (makePair path) (builtins.attrNames value)
        else if builtins.stringLength varPrefix > 0 then
          "${varPrefix}_${name}=${toString value}"
        else
          "${name}=${toString value}";
    in
    lib.lists.flatten (map (makePair [ ]) (builtins.attrNames set));
in
builtins.concatStringsSep "\n" (mapAttrsRecursiveToList attrs)
# Write the result to a file with:
#
#  attrsToEnvironmentFile = { fileName, attrs, varPrefix }:
#    pkgs.writeText fileName (attrsToEnvironmentString { inherit attrs varPrefix; });
