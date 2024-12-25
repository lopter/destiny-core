use leptos::prelude::*;
use leptos_router::components::A;

#[component]
pub fn NavBar() -> impl IntoView {
    view! {
        <nav>
            <ul>
                <li><A href="/">Louis x Kalessin</A></li>
                <li><A href="/blog">Blog</A></li>
            </ul>
        </nav>
    }
}
