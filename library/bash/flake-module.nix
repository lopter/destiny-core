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
                "--override-input" "destiny-core" "../destiny-core"
                "--override-input" "destiny-config" "../destiny-config"
                "--override-input" "clan-core" "../../src/nix/clan-core"
              );
            };
          }; done
          new_args+=("''${local_inputs[@]}");
          echo "nix" "''${new_args[@]}"
          exec nix "''${new_args[@]}"
        '';
      };
      packages.vault-shell = pkgs.writeShellScriptBin "vault-shell" ''
        cleanup() {
          shred -f ~/.vault-token
          rm -vf ~/.vault-token
        }
        trap cleanup EXIT INT QUIT TERM
        vault login
        PS1="\n(vault) ''${PS1:2}" $SHELL -i
      '';

      # Useful in the installer when nixos-enter is not cutting it:
      packages.chroot-enter =
        with pkgs;
        writeShellApplication {
          name = "chroot-enter";
          text = ''
            #!${lib.getExe' bash "sh"} -x

            target="''${1:-"/mnt"}"
            mount --bind /proc "$target/proc"
            mount --bind /sys "$target/sys"
            mount --bind /dev "$target/dev"
            mount --bind /dev/pts "$target/dev/pts"
            mount --bind /run "$target/run"
            chroot /mnt /bin/sh
          '';
          runtimeInputs = [
            bash
            coreutils
            util-linux
          ];
        };

      # Useful in the installer to mount filesystems for a specific nixos configuration:
      packages.mount-mnt =
        with pkgs;
        writeShellApplication {
          name = "mount-mnt";
          text = ''
            #!${lib.getExe' bash "sh"}

            [ $# -eq 2 ] || {
              printf >&2 "Usage: %s flake_path hostname\n" "$(basename "$0")"
              exit 1;
            }

            flake_path="$1"
            hostname="$2"

            pvscan
            vgchange -a y

            nix eval --json "''${flake_path}#nixosConfigurations.''${hostname}.config.fileSystems" \
              | jq -r '
                to_entries
                    | map("mount -o \(.value.options | join(",")) \(.value.device) /mnt\(.key)")
                    | .[]
              ' \
              | ${lib.getExe' bash "sh"} -x
          '';
          runtimeInputs = [
            bash
            jq
            nix
            lvm2
          ];
        };
    };
}
