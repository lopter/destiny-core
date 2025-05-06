pub const FEED_NAME: &str = "json";

use super::metadata::{
    DESCRIPTION,
    LANGUAGE,
    TITLE,
    blog_link,
    feed_link,
};

pub async fn handler(
    axum::extract::State(ctx): axum::extract::State<app::context::Context>,
    _request: axum::extract::Request<axum::body::Body>,
) -> Result<axum::Json<json_feed_model::Feed>, app::store::Error> {
    let mut feed = json_feed_model::Feed::new();
    feed.set_title(TITLE);
    let blog_post: Option<&str> = None;
    feed.set_home_page_url(blog_link(blog_post));
    feed.set_feed_url(feed_link(FEED_NAME));
    feed.set_description(DESCRIPTION);
    feed.set_language(LANGUAGE);
    let mut items: Vec<json_feed_model::Item> = vec![];
    for front_matter in ctx.store.index()? {
        let mut entry = json_feed_model::Item::new();
        let slug = &front_matter.slug;
        let post = ctx.store.get_post_by_slug(slug)?;
        entry.set_id(slug);
        entry.set_url(blog_link(Some(slug)));
        entry.set_title(&front_matter.metadata.title);
        entry.set_content_html(post.html_body);
        if let Some(date) = front_matter.metadata.date {
            entry.set_date_published(date.format("%Y-%m-%d"));
        }
        entry.set_tags(front_matter.metadata.tags);
        items.push(entry);
    }
    feed.set_items(items);

    Ok(axum::Json(feed))
}
