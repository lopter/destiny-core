{ ... }:
{
  perSystem =
    { pkgs, ... }:
    {
      packages.git-fetch-and-checkout = pkgs.writeShellApplication {
        name = "gfc";
        runtimeInputs = with pkgs; [ git ];
        text = ''
          branch="$(git rev-parse --abbrev-ref HEAD)"

          [ $# -ne 0 ] && {
            printf >&2 "Usage: gfc\n"
            printf >&2 "\n"
            printf >&2 'This will do "git fetch origin %s && git checkout -B %s origin/%s"\n' "$branch" "$branch" "$branch"
            exit 1;
          }

          git diff-index --quiet HEAD || {
            printf >&2 "You have uncommited changes that would be erased by this command\n"
            printf >&2 "Note that any commits in this branch not present in origin will be erased too\n"
            exit 1;
          }

          git fetch origin "$branch" && git checkout -B "$branch" "origin/$branch"
        '';
      };
      packages.n = pkgs.writeShellApplication {
        name = "n";
        runtimeInputs = with pkgs; [ nix ];
        text = ''
          new_args=()
          local_inputs=()
          for arg in "$@"; do {
            new_args+=("$arg");
            [ "$arg" = "flake" ] && {
              local_inputs+=(
                "--override-input" "multilab" "../multilab"
                "--override-input" "multilab-config" "../multilab-config"
                "--override-input" "destiny-core" "../destiny-core"
                "--override-input" "destiny-config" "../destiny-config"
                "--override-input" "clan-core" "../../src/nix/clan-core"
              );
            };
          }; done
          new_args+=("''${local_inputs[@]}");
          echo "--> nix" "''${new_args[@]}"
          exec nix "''${new_args[@]}"
        '';
      };
    };
}
