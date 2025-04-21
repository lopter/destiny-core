use leptos::prelude::*;
use leptos_router::components::A;

#[component]
pub fn NavBar() -> impl IntoView {
    view! {
        <nav>
            <ul>
                <li><A href="/">Louis Opter</A></li>
                <li><A href="/blog">Blog</A></li>
                <li><A href="https://mastodon.opter.org/@louis">Mastodon</A></li>
                <li><A href="https://bsky.app/profile/louis.opter.org">Bluesky</A></li>
                <li><A href="/about">About</A></li>
            </ul>
        </nav>
    }
}

#[component]
pub fn Footer() -> impl IntoView {
    view! {
        <footer>
            <p>
                <a href="#top"><small>{"\u{24d2}"}2025, Louis Opter (kalessin, lopter), CC BY-SA 4.0 {"\u{2191}"}</small></a>
            </p>
        </footer>
    }
}
