use axum::response::IntoResponse;

use super::metadata::{
    COPYRIGHT,
    DESCRIPTION,
    LANGUAGE,
    TITLE,
    blog_link,
    feed_link,
};

pub const FEED_NAME: &str = "rss";

pub async fn handler(
    axum::extract::State(ctx): axum::extract::State<app::context::Context>,
    _request: axum::extract::Request<axum::body::Body>,
) -> Result<axum::response::Response, app::store::Error> {
    let mut items: Vec<rss::Item> = vec![];
    for front_matter in ctx.store.index()? {
        let mut entry = rss::Item::default();
        let slug = &front_matter.slug;
        let post = ctx.store.get_post_by_slug(slug)?;
        entry.set_title(front_matter.metadata.title.to_string());
        entry.set_link(blog_link(Some(slug)));
        if let Some(date) = front_matter.metadata.date {
            entry.set_pub_date(date.format("%Y-%m-%d").to_string());
        }
        entry.set_categories(
            front_matter.metadata.tags.into_iter().map(|name| {
                rss::Category { name: name.to_string(), domain: None }
            }).collect::<Vec<rss::Category>>()
        );
        entry.set_content(post.html_body);
        items.push(entry);
    }

    let channel = rss::ChannelBuilder::default()
        .title(TITLE)
        .link(feed_link(FEED_NAME))
        .description(DESCRIPTION)
        .language(String::from(LANGUAGE))
        .copyright(String::from(COPYRIGHT))
        .items(items)
        .build();
    let response = (
        axum::http::StatusCode::OK,
        [(axum::http::header::CONTENT_TYPE, "application/rss+xml")],
        channel.to_string(),
    ).into_response();
    Ok(response)
}
