use leptos::prelude::*;
use leptos_router::components::A;

#[component]
pub fn NavBar() -> impl IntoView {
    view! {
        <nav>
            <ul>
                <li><A href="/">Louis Opter</A></li>
                <li><A href="/blog">Blog</A></li>
            </ul>
        </nav>
    }
}

#[component]
pub fn Footer() -> impl IntoView {
    view! {
        <footer>
            <p>
                <a href="#top"><small>{"\u{2191}"} Copyright {"\u{24d2}"}2025, Louis Opter (kalessin, lopter) {"\u{2191}"}</small></a>
            </p>
        </footer>
    }
}
