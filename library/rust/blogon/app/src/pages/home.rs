use leptos::prelude::*;
use leptos_router::components::A;

#[component]
pub fn Index() -> impl IntoView {
    view! {
        <main class="home">
            <nav>
                <ul>
                    <li><A href="/blog">Blog</A></li>
                    // Find images for those instead:
                    <li>GitHub</li>
                    <li>LinkedIn</li>
                    <li>Bluesky</li>
                    <li>Twitter</li>
                </ul>
            </nav>
        </main>
    }
}
