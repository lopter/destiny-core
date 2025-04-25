use leptos::prelude::*;

use crate::components::NavBar;

// TODO: Render this from a markdown document so we don't have to
// recompile the site on changes, and fix the link to "My first post":
#[component]
pub fn Index() -> impl IntoView {
    view! {
        <NavBar />
        <main class="about">
            <p>
                r#"Hi, I am an open-source contributor, with a heavy startup experience, I worked at large companies in the "Silicon Valley"."#
            </p>
            <p>
                "I take interest in both learning and teaching, writing readable and dependable code. I like writing, and at time of writing, I intend to tell you about Clan, a framework to manage a small, distributed, fleet of NixOS servers." <a href="/blog/0002-fly-io-sidecars-and-extra-luggage">"My first post"</a> " goes towards how I used Nixpkgs to do some edge networking on fly.io."
            </p>
            <p>
                r#"The artwork on this site is realized by "# <a href="https://www.atelierpentosaurus.com/">"Atelier Pentosaurus"</a> " resident Hugues Opter."
            </p>
        </main>
    }
}
