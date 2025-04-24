use leptos::prelude::*;

use crate::components::NavBar;

#[component]
pub fn Index() -> impl IntoView {
    view! {
        <main class="home">
            <img
                src="https://blogon-assets.fly.storage.tigris.dev/drawings/computer/half.webp"
                alt="A minimalistic, square, painting with a red background of a computer monitor with a keyboard an a mouse in front of it. Those peripherals are painted using a few thick blue lines."
            />
            <NavBar />
        </main>
    }
}
