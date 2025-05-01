// As of Leptos 0.8.0-rc3 the (uncompressed) wasm bundle obtained with
// `cargo leptos build --release` and Rust 1.88 nightly, weighs about 597K.
#[wasm_bindgen::prelude::wasm_bindgen]
pub fn hydrate() {
    use app::*;
    console_error_panic_hook::set_once();
    leptos::mount::hydrate_body(App);
}
