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
                <a href="/blog/feed.rss" rel="external"><img src="/blog-icons/feed-rss.svg" alt="RSS Feed" /></a>
                <a href="/blog/feed.json" rel="external"><img src="/blog-icons/feed-json.svg" alt="JSON Feed" /></a>
                <A href="#top">{"\u{24d2}"}2025, Louis Opter (kalessin, lopter), text CC BY-SA 4.0, images all rights reserved {"\u{2191}"}</A>
            </p>
        </footer>
    }
}
