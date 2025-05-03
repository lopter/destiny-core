use leptos::prelude::*;

use app::store;

mod feeds;

const LEPTOS_SERVER_FN_URL_PATH: &str = "/blog/api/{*fn_name}";

#[tokio::main]
async fn main() {
    use leptos_axum::{generate_route_list, LeptosRoutes};

    env_logger::init();

    let conf = get_configuration(None).unwrap();
    let addr = conf.leptos_options.site_addr;
    let leptos_options = conf.leptos_options;
    let ctx = app::context::Context {
        leptos_options: leptos_options.clone(),
        store: store::Store::new(
            std::path::PathBuf::from(env!("BLOGON_BLOG_STORE_PATH")),
            leptos_options.env == Env::PROD,
        ),
    };
    // Generate the list of routes in your Leptos App
    let routes = generate_route_list(app::App);
    let ctx_fn = {
        let ctx = ctx.clone();
        move || provide_context(ctx.store.clone())
    };
    let app_fn = {
        let ctx = ctx.clone();
        move || app::shell(ctx.leptos_options.clone())
    };

    let leptos_server_fn_method_router =
        axum::routing::get(leptos_server_fn_axum_handler)
            .post(leptos_server_fn_axum_handler);
    let json_feed_method_router = axum::routing::get(feeds::json::handler);
    let rss_feed_method_router = axum::routing::get(feeds::rss::handler);
    let app = axum::Router::new()
        .route(LEPTOS_SERVER_FN_URL_PATH, leptos_server_fn_method_router)
        .route(feeds::json::URL_PATH, json_feed_method_router)
        .route(feeds::rss::URL_PATH, rss_feed_method_router)
        .leptos_routes_with_context(&ctx, routes, ctx_fn, app_fn)
        // We could also pass the context to file_and_error_handler
        .fallback(leptos_axum::file_and_error_handler::<app::context::Context, _>(app::shell))
        .with_state(ctx);

    // run our app with hyper
    // `axum::Server` is a re-export of `hyper::Server`
    log::info!("listening in {:?} on http://{}", &leptos_options.env, &addr);
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app.into_make_service())
        .await
        .unwrap();
}

async fn leptos_server_fn_axum_handler(
    axum::extract::State(ctx): axum::extract::State<app::context::Context>,
    request: axum::extract::Request<axum::body::Body>,
) -> impl axum::response::IntoResponse {
    let additional_context = move || { provide_context(ctx.store.clone()); };
    leptos_axum::handle_server_fns_with_context(additional_context, request)
        .await
}
