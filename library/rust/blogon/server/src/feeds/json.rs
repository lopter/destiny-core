pub const URL_PATH: &str = "/blog/feed.json";

use super::metadata::{
    BLOG_PATH,
    DESCRIPTION,
    LANGUAGE,
    TITLE,
    link,
};

pub async fn handler(
    axum::extract::State(ctx): axum::extract::State<app::context::Context>,
    _request: axum::extract::Request<axum::body::Body>,
) -> Result<axum::Json<json_feed_model::Feed>, app::store::Error> {
    let mut feed = json_feed_model::Feed::new();
    feed.set_title(TITLE);
    feed.set_home_page_url(link(BLOG_PATH));
    feed.set_feed_url(link(URL_PATH));
    feed.set_description(DESCRIPTION);
    feed.set_language(LANGUAGE);
    let mut items: Vec<json_feed_model::Item> = vec![];
    for front_matter in ctx.store.index()? {
        let mut entry = json_feed_model::Item::new();
        let slug = &front_matter.slug;
        let post = ctx.store.get_post_by_slug(slug)?;
        entry.set_id(slug);
        entry.set_url(link(format!("{}/{}", BLOG_PATH, slug).as_str()));
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
