pub mod components;
pub mod pages;
pub mod store;

use leptos::prelude::*;
use leptos_meta::{provide_meta_context, MetaTags, Stylesheet, Title};
use leptos_router::{
    components::{Route, Router, Routes},
    ParamSegment, SsrMode, StaticSegment,
};

pub fn shell(options: LeptosOptions) -> impl IntoView {
    view! {
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1"/>
                <meta name="description" content="Hello, I am Louis Opter, a generalist software engineer with an eye for: distributed systems, build systems (Nix, Bazel), self-hosting. Proficient in Python, Golang, and C. AKA, kalessin, lopter."/>
                <AutoReload options=options.clone() />
                <HydrationScripts options/>
                <MetaTags/>
            </head>
            <body id="#top">
                <App/>
            </body>
        </html>
    }
}

#[component]
pub fn App() -> impl IntoView {
    // Provides context that manages stylesheets, titles, meta tags, etc.
    provide_meta_context();

    use pages;

    view! {
        // injects a stylesheet into the document <head>
        // id=leptos means cargo-leptos will hot-reload this stylesheet
        <Stylesheet id="leptos" href="/pkg/blogon.css"/>

        // sets the document title
        <Title formatter=|text: String| {
            if text.is_empty() {
                format!("Louis Opter (kalessin)")
            } else {
                format!("{} - Louis Opter (kalessin)", text)
            }
        }/>

        // content for this welcome page
        <Router>
            <Routes fallback=|| "Page not found.".into_view()>
                // Let's use async rendering so that we fully render on the server since this
                // is really static content. However, this will suck if we ever add comments,
                // since we'll want to actually load those asynchronously.
                // My understanding is that SsrMode::PartiallyBlocked & Resource::new_blocking
                // should address that, but it does not seem to work.
                <Route
                    path=StaticSegment("")
                    view=pages::home::Index
                    ssr=SsrMode::Async
                />
                <Route
                    path=StaticSegment("blog")
                    view=pages::blog::Index
                    ssr=SsrMode::PartiallyBlocked
                />
                <Route
                    path=(StaticSegment("blog"), ParamSegment("slug"))
                    view=pages::blog::Post
                    ssr=SsrMode::PartiallyBlocked
                />
            </Routes>
        </Router>
    }
}
