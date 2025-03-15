use leptos::prelude::*;
use leptos_router::components::A;

#[component]
pub fn Index() -> impl IntoView {
    view! {
        <main class="home">
            <nav>
                <ul>
                    <li><A href="/blog">Blog</A></li>
                    <li>Contact</li>
                    <li>Resume</li>
                </ul>
            </nav>
        </main>
    }
}
