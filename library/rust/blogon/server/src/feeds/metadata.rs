const BASE_URL: &str = "https://www.kalessin.fr";
const BLOG_PATH: &str = "/blog";

pub const COPYRIGHT: &str = "CC BY-SA 4.0";
pub const DESCRIPTION: &str = TITLE;
pub const LANGUAGE: &str = "en";
pub const TITLE: &str = "Louis Opter (kalessin) :: Blog";

pub fn blog_link(slug: Option<&str>) -> String {
    slug.map_or_else(
        || String::from(BASE_URL) + BLOG_PATH,
        |slug| format!("{}/{}/{}", BASE_URL, BLOG_PATH, slug)
    )
}

pub fn feed_link(name: &str) -> String {
    format!("{}{}", BASE_URL, feed_path(name))
}

pub fn feed_path(name: &str) -> String {
    format!("{}/feed.{}", BLOG_PATH, name)
}
