const BASE_URL: &str = "https://www.kalessin.fr";

pub const BLOG_PATH: &str = "/blog";
pub const COPYRIGHT: &str = "CC BY-SA 4.0";
pub const DESCRIPTION: &str = TITLE;
pub const LANGUAGE: &str = "en";
pub const TITLE: &str = "Louis Opter (kalessin) :: Blog";

pub fn link(path: &str) -> String {
    String::from(BASE_URL) + path
}


