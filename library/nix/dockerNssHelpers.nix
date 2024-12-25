# Basically a copy of the relevant parts from docker.nix in Nix's repository:
lib: pkgs: groups: users:
let
  userToPasswd = (
    k:
    {
      uid,
      gid,
      home ? "/var/empty",
      description ? "",
      shell ? "/bin/false",
      ...
    }:
    "${k}:x:${toString uid}:${toString gid}:${description}:${home}:${shell}"
  );
  passwdContents = (lib.concatStringsSep "\n" (lib.attrValues (lib.mapAttrs userToPasswd users)));

  userToShadow = k: { ... }: "${k}:!:1::::::";
  shadowContents = (lib.concatStringsSep "\n" (lib.attrValues (lib.mapAttrs userToShadow users)));

  # Map groups to members
  # {
  #   group = [ "user1" "user2" ];
  # }
  groupMemberMap = (
    let
      # Create a flat list of user/group mappings
      mappings = (
        builtins.foldl' (
          acc: user:
          let
            groups = users.${user}.groups or [ ];
          in
          acc
          ++ map (group: {
            inherit user group;
          }) groups
        ) [ ] (lib.attrNames users)
      );
    in
    (builtins.foldl' (
      acc: v:
      acc
      // {
        ${v.group} = acc.${v.group} or [ ] ++ [ v.user ];
      }
    ) { } mappings)
  );

  groupToGroup =
    k:
    { gid, ... }:
    let
      members = groupMemberMap.${k} or [ ];
    in
    "${k}:x:${toString gid}:${lib.concatStringsSep "," members}";
  groupContents = (lib.concatStringsSep "\n" (lib.attrValues (lib.mapAttrs groupToGroup groups)));
in
pkgs.runCommand "usergroups"
  {
    inherit passwdContents groupContents shadowContents;
    passAsFile = [
      "passwdContents"
      "groupContents"
      "shadowContents"
    ];
    allowSubstitutes = false;
    preferLocalBuild = true;
  }
  ''
    set -x
    mkdir -p $out/etc

    cat $passwdContentsPath > $out/etc/passwd
    echo "" >> $out/etc/passwd

    cat $groupContentsPath > $out/etc/group
    echo "" >> $out/etc/group

    cat $shadowContentsPath > $out/etc/shadow
    echo "" >> $out/etc/shadow
  ''
