{
  description = "The code library supporting a Nix'ed homelab";

  inputs = {
    clan-core.url = "git+https://git.clan.lol/clan/clan-core";
    # clan-core.url = "git+file:///stash/home/kal/cu/src/nix/clan-core";
    clan-core.inputs.nixpkgs.follows = "nixpkgs";
    clan-core.inputs.flake-parts.follows = "flake-parts";

    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";

    nixpkgs.url = "git+https://github.com/lopter/nixpkgs?ref=nixos-unstable-lo-patches&shallow=1";
    # nixpkgs.url = "/stash/home/kal/cu/src/nix/nixpkgs";

    nixpkgs-unfree.url = "github:numtide/nixpkgs-unfree";
    nixpkgs-unfree.inputs.nixpkgs.follows = "nixpkgs";

    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";

    fenix.url = "github:nix-community/fenix/main";
    fenix.inputs.nixpkgs.follows = "nixpkgs";
    fenix.inputs.rust-analyzer-src.follows = "";
    rust-manifest = {
      # Rust 1.86.0
      type = "file";
      url = "https://static.rust-lang.org/dist/2025-04-03/channel-rust-stable.toml";
      flake = false;
    };
    rust-manifest-nightly = {
      # Rust 1.87.0-nightly
      type = "file";
      url = "https://static.rust-lang.org/dist/2025-04-28/channel-rust-nightly.toml";
      flake = false;
    };
    crane.url = "github:ipetkov/crane";
    advisory-db.url = "github:rustsec/advisory-db";
    advisory-db.flake = false;

    # devenv inputs:
    devenv.url = "github:cachix/devenv";
    devenv.inputs.nixpkgs.follows = "nixpkgs";
    nix2container.url = "github:nlewo/nix2container";
    nix2container.inputs.nixpkgs.follows = "nixpkgs";
    mk-shell-bin.url = "github:rrbutani/nix-mk-shell-bin";
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
        ./library/python/hass-pam-authenticate/flake-module.nix
        ./library/python/toolbelt/flake-module.nix

        ./library/rust/blogon/flake-module.nix
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
            { rustToolchain }:
            let
              craneLib = inputs.crane.mkLib pkgs;
            in
            (craneLib.overrideToolchain rustToolchain).overrideScope (
              _final: _prev: {
                # The version of wasm-bindgen-cli needs to match the version in
                # Cargo.lock. You can unpin this if your nixpkgs commit contains the
                # appropriate wasm-bindgen-cli version.
                #
                # I cargo-culted this from the crane template for trunk.
                wasm-bindgen-cli = pkgs.wasm-bindgen-cli.override {
                  version = "0.2.100";
                  hash = "";
                  cargoHash = "";
                };
              }
            );

          devenv.shells.default = {
            name = "default";

            # Enable C for Rust, since we are setting up our toolchain manually.
            languages.c.enable = true;

            packages =
              [
                config.treefmt.build.wrapper
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
                  extraPythonPackages = package.dependencies ++ [
                    pkgs.python3Packages.types-pyyaml
                  ];
                  options = [
                    "--enable-incomplete-feature=NewGenericSyntax"
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
            programs.rustfmt.enable = true;
          };
        };
    };
}
