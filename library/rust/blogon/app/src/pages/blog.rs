use anyhow::Result;
use leptos::prelude::*;
use leptos_router::components::A;
use std::path::PathBuf;

use crate::store;

#[component]
pub fn Index() -> impl IntoView {
    let index = Resource::new_blocking(|| (), move |_| async { get_store_index().await });

    /* This + Transition/ErrorBoundary does not work as expected in SsrMode::PartiallyBlocked:
    let front_matters = move || {
        Suspend::new(async move {
            index
                .await
                .map(|front_matters| {
                    if front_matters.is_empty() {
                        leptos::either::Either::Left(view! { "Loading…" })
                    } else {
                        leptos::either::Either::Right(
                            front_matters
                                .into_iter()
                                .map(|item| view! { <li>{item.title.clone()}</li> })
                                .collect::<Vec<_>>()
                        )
                    }
                })
        })
    };
    */

    view! {
        <nav>
        {move || match index.get() {
            None => leptos::either::EitherOf3::A(view! { "Loading…" }.into_view()),
            Some(Ok(list)) => leptos::either::EitherOf3::B(
                view! {
            <ul>
                {list
                    .into_iter()
                    .map(|item| {
                        let url = format!("/blog/{}", item.slug);
                        let name = item.metadata.title.clone();
                        view! { <li><A href={ url }>{ name }</A></li> }
                    })
                    .collect_view()}
            </ul>
            }.into_view()),
            Some(Err(err)) => leptos::either::EitherOf3::C(view! {
                {format!("Could not load index: {}", err.to_string())}
            }.into_view()),
        }}
    /*
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
    */
        </nav>
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

    view! {
        {move || match post.get() {
            None => leptos::either::EitherOf3::A(view! { <p>{"Loading…"}</p> }.into_view()),
            // setup some nav with the ToC
            Some(Ok(post)) => leptos::either::EitherOf3::B(view! {
                <article inner_html=post.html_body></article>
            }.into_view()),
            Some(Err(err)) => leptos::either::EitherOf3::C(view! {
                <p>{format!("Could not load index: {}", err.to_string())}</p>
            }.into_view()),
        }}
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
