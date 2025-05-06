{ lib, ... }:
{
  perSystem =
    { pkgs, setupCraneLib, setupRustToolchain, ... }:
    let
      rustToolchain = setupRustToolchain {
        nightly = true;
        withWasm32 = true;
      };
      craneLib = setupCraneLib { inherit rustToolchain; };
    in
    {
      packages.blogon =
      let
        pname = "blogon";
        src = lib.cleanSourceWith {
          src = ./.;
          filter = path: type:
            (lib.hasInfix "/public/" path) ||
            (lib.hasInfix "/style/" path) ||
            (craneLib.filterCargoSources path type)
          ;
        };
        commonArgs = {
          inherit pname src;
          version = "0.0.1";
          strictDeps = true;
          buildInputs = lib.optionals pkgs.stdenv.isDarwin [
            pkgs.libiconv
          ];
        };
        cargoArtifacts = craneLib.buildDepsOnly commonArgs;
      in
      craneLib.buildPackage (commonArgs // {
          inherit cargoArtifacts;
          buildPhaseCargoCommand = "cargo leptos build --release -vvv";
          cargoTestCommand = "cargo leptos test --release -vvv";
          nativeBuildInputs = with pkgs; [
            binaryen
            cargo-leptos
            dart-sass
            makeWrapper
          ];
          doCheck = false;
          doNotPostBuildInstallCargoBinaries = true;
          installPhaseCommand = ''
            mkdir -p $out/bin
            cp target/release/server $out/bin/${pname}
            cp -r target/site $out/bin/
            wrapProgram $out/bin/${pname} \
              --set LEPTOS_SITE_ROOT $out/bin/site
          '';
          env = {
            BLOGON_BLOG_STORE_PATH = "/var/lib/blogon/posts";
          };
      });

      devenv.shells.blogon = {
        name = "blogon";

        packages = with pkgs; [
          rustToolchain

          binaryen

          cargo-generate
          cargo-leptos
          cargo-watch # cargo leptos does not know how watch tests

          dart-sass

          playwright-test
        ];

        env = {
          LEPTOS_END2END_CMD = "${pkgs.playwright-test}/bin/playwright test";
          PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";

          BLOGON_BLOG_STORE_PATH = "/stash/home/kal/syncthing/archives/blogon/posts";

          RUST_BACKTRACE = "1";
          RUST_LOG = "DEBUG";
        };
      };
    };

}
