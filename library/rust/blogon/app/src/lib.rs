pub mod components;
#[cfg(feature = "ssr")]
pub mod context;
pub mod pages;
pub mod store;

use leptos::prelude::*;
use leptos::nonce::use_nonce;
use leptos_meta::{provide_meta_context, MetaTags, Stylesheet, Title};
use leptos_router::{
    components::{Route, Router, Routes},
    ParamSegment, SsrMode, StaticSegment,
};

const WEBSITE_ID: &str = "b9663eae-790f-4252-9d3f-165f1efbf460";

pub fn shell(options: LeptosOptions) -> impl IntoView {
    view! {
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1"/>
                <meta name="description" content="Hello, I am Louis Opter, a generalist software engineer with an eye for: distributed systems, build systems (Nix, Bazel), self-hosting. Proficient in Python, Golang, and C. AKA, kalessin, lopter."/>
                <meta
                    http-equiv="content-security-policy"
                    content=move || {
                        use_nonce()
                            .map(|nonce| {
                                format!(
                                    "default-src 'none'; \
                                    connect-src 'self' https://api-gateway.umami.dev/; \
                                    font-src 'self'; \
                                    img-src 'self' https://blogon-assets.fly.storage.tigris.dev/; \
                                    script-src 'strict-dynamic' 'nonce-{nonce}' 'wasm-unsafe-eval'; \
                                    style-src 'self' 'nonce-{nonce}';"
                                )
                            })
                            .unwrap_or_default()
                    }
                />
                <script defer src="/dramametry.js" data-website-id=WEBSITE_ID nonce=use_nonce()></script>
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
        <Stylesheet id="leptos" href="/blog-pkg/blogon.css"/>

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
                <Route
                    path=StaticSegment("")
                    view=pages::home::Index
                    // Let's use async rendering so that we fully render
                    // on the server since this is really static content.
                    ssr=SsrMode::Async
                />
                <Route
                    path=StaticSegment("about")
                    view=pages::about::Index
                    ssr=SsrMode::PartiallyBlocked
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
