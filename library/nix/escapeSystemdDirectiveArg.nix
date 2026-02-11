# Quotes a string for use in systemd unit settings whose values are parsed as
# whitespace-separated lists by extract_first_word() with EXTRACT_UNQUOTE,
# such as BindPaths=, BindReadOnlyPaths=, TemporaryFileSystem=,
# ReadWritePaths=, ReadOnlyPaths=, InaccessiblePaths=, and similar.
#
# Within the double-quoted result only \" and \\ are used as escape sequences
# which is all that EXTRACT_UNQUOTE recognizes.
#
# Note: this is NOT suitable for Exec* lines which use EXTRACT_CUNESCAPE, use
# escapeSystemdExecArg from nixpkgs for those.
#
# Type: escapeSystemdDirectiveArg :: (String | Path) -> String
#
# Example:
#   escapeSystemdDirectiveArg "/path/with spaces"
#   => ''"/path/with spaces"''
#
#   escapeSystemdDirectiveArg "/simple/path"
#   => ''"/simple/path"''
lib:
arg:
let
  s =
    if lib.isPath arg then
      toString arg
    else if lib.isString arg then
      arg
    else
      throw "escapeSystemdDirectiveArg only allows strings and paths";
in
"\"" + lib.replaceStrings [ "\\" "\"" ] [ "\\\\" "\\\"" ] s + "\""
