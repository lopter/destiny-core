use anyhow::Result;
use leptos::prelude::*;
use leptos_meta::Title;
use leptos_router::components::A;
use std::path::PathBuf;

use crate::components::{Footer, NavBar};
use crate::store;

#[component]
pub fn Index() -> impl IntoView {
    let index = Resource::new_blocking(|| (), move |_| async { get_store_index().await });

    let front_matters = move || {
        Suspend::new(async move {
            index
                .await
                .map(|front_matters| {
                    if front_matters.is_empty() {
                        leptos::either::Either::Left(view! {
                            "Something has yet to be posted…"
                        })
                    } else {
                        leptos::either::Either::Right(
                            front_matters
                                .into_iter()
                                .map(|item| {
                                    let date = item.metadata.date.as_ref().map_or(
                                        String::from("Unpublished"),
                                        |dt| dt.format("%Y-%m-%d").to_string(),
                                    );
                                    view! {
                                        <PostDetails
                                            slug={ item.slug.clone() }
                                            title={ item.metadata.title.clone() }
                                            date={ date }
                                            tags={ item.metadata.tags.clone() }
                                        />
                                    }
                                })
                                .collect::<Vec<_>>()
                        )
                    }
                })
        })
    };

    view! {
        <Title text="Blog index" />
        <NavBar />
        <main class="blog-index">
        <h1>Blog index</h1>
        <nav>
        <Transition fallback=move || view! { "Loading…" }>
            <ErrorBoundary fallback=move |errors| {
                view! {
                    <h1>"Errors"</h1>
                    {move || {
                        errors()
                            .into_iter()
                            .map(|error| {
                                view! { <p>"Error: " {error.1.to_string()}</p> }
                            })
                            .collect::<Vec<_>>()
                    }}
                }
            }>
            <ul>
                {front_matters}
            </ul>
            </ErrorBoundary>
        </Transition>
        </nav>
        </main>
        <Footer />
    }
}

#[component]
pub fn PostDetails(slug: String, title: String, date: String, tags: Vec<String>) -> impl IntoView {
    view! {
        <li>
            { format!("{}: ", date) }<A href={ format!("/blog/{}", slug) }>{ title }</A>
            <div class="tags-list">
                <span>"Tags:"</span>
                <ul>
                {
                    tags.into_iter()
                        .map(|tag| view! { <li><span class="tag">{ tag }</span></li> })
                        .collect_view()
                }
                </ul>
            </div>
        </li>
    }
}

#[server(GetStoreIndex, "/blog", "GetJson", "index")]
pub async fn get_store_index() -> Result<Vec<store::FrontMatter>, ServerFnError> {
    let path = PathBuf::from(env!("BLOGON_BLOG_STORE_PATH"));
    let store = store::Store::open(path);
    store
        .index()
        .map_err(|e| ServerFnError::ServerError(e.to_string()))
}

#[component]
pub fn Post() -> impl IntoView {
    let params = leptos_router::hooks::use_params_map();

    let post = Resource::new_blocking(
        move || params.read().get("slug").unwrap_or_default(),
        move |slug| async {
            if slug.is_empty() {
                return Err(ServerFnError::MissingArg(String::from("empty slug")));
            }
            get_post_by_slug(slug).await
        },
    );

    let contents = Suspend::new(async move {
        post
            .await
            .map(|post| {
                let title = post.front_matter.metadata.title;
                view! {
                    <Title text={ title.clone() } />
                    <h1>{ title }</h1>
                    <article inner_html=post.html_body></article>
                }
            })
    });

    view! {
        <Title text="Blog Post" />
        <NavBar />
        <main class="blog-post">
        <Transition fallback=move || view! { "Loading…" }>
            <ErrorBoundary fallback=move |errors| {
                view! {
                    <h1>"Errors"</h1>
                    {move || {
                        errors()
                            .into_iter()
                            .map(|error| {
                                view! { <p>"Error: " {error.1.to_string()}</p> }
                            })
                            .collect::<Vec<_>>()
                    }}
                }
            }>
            {contents}
            </ErrorBoundary>
        </Transition>
        </main>
        <Footer />
    }
}

#[server(GetPostBySlug, "/blog", "GetJson", "post")]
pub async fn get_post_by_slug(slug: String) -> Result<store::Post, ServerFnError> {
    // TODO: voir comment avoir store dans une sorte de contexte
    let path = PathBuf::from(env!("BLOGON_BLOG_STORE_PATH"));
    let store = store::Store::open(path);
    store
        .get_post_by_slug(&slug)
        .map_err(|e| ServerFnError::ServerError(e.to_string()))
}
