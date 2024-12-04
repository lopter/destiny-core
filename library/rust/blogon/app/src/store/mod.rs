use std::path::{Path, PathBuf};

pub mod errors;
mod front_matter;
mod post;

pub use errors::{Error, Result};
pub use front_matter::FrontMatter;
pub use post::Post;

pub struct Store {
    path: PathBuf,
}

impl Store {
    pub fn open(path: PathBuf) -> Self {
        Store { path }
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
            let path = if metadata.file_type().is_dir() {
                let mut path = entry.path();
                path.push("post.md");
                path
            } else {
                entry.path()
            };
            index.push(FrontMatter::read(&path)?);
        }
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
        let parts = [self.path.as_path(), Path::new(file_name.as_str())];
        let file_path: PathBuf = parts.iter().collect();
        log::info!("slug \"{}\" points to file \"{}\"", slug, file_name);
        post::render(&file_path)
    }
}
