use leptos::prelude::LeptosOptions;

use crate::store;

#[derive(Clone, Debug)]
pub struct Context { // Could be called "AppState"
    pub leptos_options: LeptosOptions,
    pub store: store::Store,
}

// Looks like we could use `derive(FromRef)` on `Context` if we enabled the macros feature on axum.
impl axum::extract::FromRef<Context> for LeptosOptions {
    fn from_ref(value: &Context) -> Self {
        value.leptos_options.clone()
    }
}
