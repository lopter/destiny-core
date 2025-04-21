use leptos::prelude::*;

use crate::components::NavBar;

#[component]
pub fn Index() -> impl IntoView {
    view! {
        <main class="home">
            <img src="/computer.png"/>
            <NavBar />
        </main>
    }
}
