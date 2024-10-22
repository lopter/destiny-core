{
  description = "The code library supporting a Nix'ed homelab";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";

    nixpkgs.url = "github:lopter/nixpkgs/nixos-unstable-lo-patches";
    # nixpkgs.url = "/stash/home/kal/cu/src/nix/nixpkgs";

    nixpkgs-unfree.url = "github:numtide/nixpkgs-unfree";
    nixpkgs-unfree.inputs.nixpkgs.follows = "nixpkgs";

    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";

    fenix.url = "github:nix-community/fenix/main";
    fenix.inputs.nixpkgs.follows = "nixpkgs";
    fenix.inputs.rust-analyzer-src.follows = "";
    rust-manifest = {
      # Rust 1.77.2
      type = "file";
      url = "https://static.rust-lang.org/dist/2024-04-09/channel-rust-stable.toml";
      flake = false;
    };
    rust-manifest-nightly = {
      # Rust 1.82.0-nightly
      type = "file";
      url = "https://static.rust-lang.org/dist/2024-07-27/channel-rust-nightly.toml";
      flake = false;
    };
    crane.url = "github:ipetkov/crane";
    advisory-db.url = "github:rustsec/advisory-db";
    advisory-db.flake = false;

    # devenv inputs:
    devenv.url = "github:cachix/devenv/v1.3";
    devenv.inputs.nixpkgs.follows = "nixpkgs";
    nix2container.url = "github:nlewo/nix2container";
    nix2container.inputs.nixpkgs.follows = "nixpkgs";
    mk-shell-bin.url = "github:rrbutani/nix-mk-shell-bin";
    # Avoid the use of nix --impure, see https://github.com/cachix/devenv/pull/1018
    # but the UX is still not really there, e.g. you still need --impure to run
    # something like `nix flake show`. I guess this approach bets on the fact
    # that devenv is for interactive use.
    devenv-root.url = "file+file:///dev/null"; # this url is set/overriden from .envrc
    devenv-root.flake = false;
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        inputs.devenv.flakeModule
        inputs.treefmt-nix.flakeModule

        ./library/bash/flake-module.nix

        ./library/nix/flake-module.nix

        ./library/python/acl_watcher/flake-module.nix
        ./library/python/backups/flake-module.nix
        ./library/python/toolbelt/flake-module.nix
      ];
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      perSystem =
        {
          config,
          self',
          inputs',
          pkgs,
          system,
          setupRustToolchain,
          ...
        }:
        {
          # Looks like this has some setbacks see:
          #
          # https://discourse.nixos.org/t/using-nixpkgs-legacypackages-system-vs-import/17462/8
          # https://zimbatm.com/notes/1000-instances-of-nixpkgs
          _module.args.pkgs = import inputs.nixpkgs {
            inherit system;
            overlays = import ./third_party/overlays.nix;
          };

          # Maybe this could be done from a separate module that people could
          # import from their `perSystem` function in their `flake.nix`.
          _module.args.setupRustToolchain =
            { nightly, withWasm32 }:
            let
              fenixPkgs = inputs'.fenix.packages;
              hostRustToolchain =
                if nightly == false then
                  (fenixPkgs.fromManifestFile inputs.rust-manifest)
                else
                  (fenixPkgs.fromManifestFile inputs.rust-manifest-nightly);
              # See https://rust-lang.github.io/rustup/concepts/components.html:
              hostRustComponents = with hostRustToolchain; [
                # I have been using stable manifests, not all those components
                # might be available on other types of releases.
                cargo
                clippy
                llvm-tools
                rust-analyzer
                rustc
                rust-docs
                rustfmt
                rust-src
                rust-std
              ];
              # Let's add (combine with) wasm32-unknown-unknown.rust-std
              # so that we can use `trunk` to build the frontend:
              wasmTarget = fenixPkgs.targets.wasm32-unknown-unknown;
              wasmRustToolchain =
                if nightly == false then
                  (wasmTarget.fromManifestFile inputs.rust-manifest)
                else
                  (wasmTarget.fromManifestFile inputs.rust-manifest-nightly);
            in
            fenixPkgs.combine (
              hostRustComponents ++ pkgs.lib.optionals withWasm32 [ wasmRustToolchain.rust-std ]
            );
          _module.args.setupCraneLib =
            { nightly, withWasm32 }:
            let
              craneLib = inputs.crane.mkLib pkgs;
              rustToolchain = setupRustToolchain { inherit nightly withWasm32; };
            in
            (craneLib.overrideToolchain rustToolchain).overrideScope (
              _final: _prev: {
                # The version of wasm-bindgen-cli needs to match the version in
                # Cargo.lock. You can unpin this if your nixpkgs commit contains the
                # appropriate wasm-bindgen-cli version.
                #
                # I cargo-culted this from the crane template for trunk.
                wasm-bindgen-cli = pkgs.wasm-bindgen-cli.override {
                  version = "0.2.93";
                  hash = "sha256-DDdu5mM3gneraM85pAepBXWn3TMofarVR4NbjMdz3r0=";
                  cargoHash = "sha256-birrg+XABBHHKJxfTKAMSlmTVYLmnmqMDfRnmG6g/YQ=";
                };
              }
            );

          devenv.shells.default = {
            devenv.root =
              let
                devenvRootFileContent = builtins.readFile inputs.devenv-root.outPath;
              in
              pkgs.lib.mkIf (devenvRootFileContent != "") devenvRootFileContent;

            name = "default";

            # Enable C for Rust, since we are setting up our toolchain manually.
            languages.c.enable = true;

            packages =
              [
                config.treefmt.build.wrapper

                (setupRustToolchain {
                  nightly = false;
                  withWasm32 = false;
                })
              ]
              ++ (with pkgs; [
                cfssl
                gnused
                shellcheck
                sops
                ssh-to-age
              ])
              ++ (with self'.packages; [
                git-fetch-and-checkout
                toolbelt
              ]);
          };

          treefmt = {
            projectRootFile = ".git/config";

            programs.shellcheck.enable = true;

            programs.mypy.enable = true;
            programs.nixfmt.enable = true;
            programs.nixfmt.package = pkgs.nixfmt-rfc-style;
            programs.deadnix.enable = true;
            settings.global.excludes = [
              "*.png"
              "*.jpeg"
              "*.gitignore"
              ".vscode/*"
              "*.toml"
              "*.age"
            ];
            programs.mypy.directories =
              let
                mkConfig = package: {
                  extraPythonPackages = [
                    package
                    pkgs.python3Packages.types-pyyaml
                  ];
                  options = [
                    "--explicit-package-bases"
                    "--exclude"
                    "setup.py"
                  ];
                };
              in
              {
                "library/python/acl_watcher" = mkConfig self'.packages.acl-watcher;
                "library/python/backups" = mkConfig self'.packages.backups;
                "library/python/toolbelt" = mkConfig self'.packages.toolbelt;
              };
            programs.ruff.check = true;
            programs.ruff.format = true;
          };
        };
    };
}
