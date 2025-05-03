#[cfg(feature = "ssr")]
pub mod errors;
mod front_matter;
mod post;

#[cfg(feature = "ssr")]
pub use errors::{Error, Result};
pub use front_matter::FrontMatter;
pub use post::Post;

#[cfg(feature = "ssr")]
#[derive(Clone, Debug)]
pub struct Store {
    path: std::path::PathBuf,
    is_running_in_prod: bool,
}

#[cfg(feature = "ssr")]
impl Store {
    pub fn new(path: std::path::PathBuf, is_running_in_prod: bool) -> Self {
        Self {
            path,
            is_running_in_prod,
        }
    }

    pub fn index(&self) -> Result<Vec<FrontMatter>> {
        let mut index = vec![];

        let directory = self.path.read_dir().map_err(|error| Error::IO {
            error,
            path: self.path.clone(),
        })?;
        for entry in directory {
            let entry = entry.map_err(|error| Error::IO {
                error,
                path: self.path.clone(),
            })?;
            let metadata = entry.metadata().map_err(|error| Error::IO {
                error,
                path: self.path.clone(),
            })?;
            if let Some(file_name) = entry.file_name().to_str() {
                let leading_digits = file_name
                    .chars()
                    .take_while(|c| c.is_digit(10))
                    .count();
                if leading_digits < 4 || !file_name.ends_with(".md") {
                    continue;
                }
            } else {
                log::warn!("Invalid utf-8 filename in the store: {:?}", entry.file_name());
                continue;
            }
            let path = if metadata.file_type().is_dir() {
                let mut path = entry.path();
                path.push("post.md");
                path
            } else {
                entry.path()
            };
            let front_matter = FrontMatter::read(&path)?;
            if !self.is_running_in_prod || front_matter.metadata.date.is_some() {
                index.push(front_matter);
            }
        }

        index.sort_by(|lhs, rhs| {
            use core::cmp::Ordering;
            match (lhs.metadata.date, rhs.metadata.date) {
                (Some(lhd), Some(rhd)) => lhd.cmp(&rhd),
                (Some(_), None) => Ordering::Less,
                (None, Some(_)) => Ordering::Greater,
                (None, None) => lhs.slug.cmp(&rhs.slug),
            }.reverse()
        });

        Ok(index)
    }

    pub fn get_post_by_slug(&self, slug: &str) -> Result<Post> {
        let mut parts = slug.split('-');
        let number = parts
            .next()
            .ok_or(Error::NotFound {
                slug: String::from(slug),
                error: String::from("empty slug?"),
            })?
            .parse::<u32>()
            .map_err(|error| Error::NotFound {
                slug: String::from(slug),
                error: error.to_string(),
            })?;
        let post_name = parts.collect::<Vec<&str>>().join("_");
        let file_name = format!("{number:04}_{post_name}.md");
        let parts = [self.path.as_path(), std::path::Path::new(file_name.as_str())];
        let file_path: std::path::PathBuf = parts.iter().collect();
        log::info!("slug \"{}\" points to file \"{}\"", slug, file_name);
        post::render(&file_path)
    }

    /*
    fn iter_posts(&self) -> ??? {
        self.index().map(|index| {
            index.into_iter()
                .filter_map(|front_matter| {
                    self.get_post_by_slug(front_matter.slug.as_str())
                        .map_or_else(
                            |post| Some(post),
                            |error| {
                                log::warn!("Could not iter post `{}`: `{:?}`", front_matter.slug, error);
                                None
                            },
                        )
                })
        })
    }
    */
}
