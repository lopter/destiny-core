{
  perSystem =
    { pkgs, setupRustToolchain, ... }:
    {
      devenv.shells.blogon = {
        name = "blogon";

        packages = with pkgs; [
          (setupRustToolchain {
            nightly = true;
            withWasm32 = true;
          })

          cargo-generate
          cargo-leptos
          cargo-watch # cargo leptos does not know how watch tests

          dart-sass

          playwright-test

        ];

        env = {
          LEPTOS_END2END_CMD = "${pkgs.playwright-test}/bin/playwright test";
          PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";

          BLOGON_BLOG_STORE_PATH = "/stash/home/kal/cu/projs/multilab-config/archive/blogon";

          RUST_LOG = "DEBUG";
        };
      };
    };

}
