use std::path::PathBuf;

#[derive(thiserror::Error, Debug)]
pub enum Error {
    #[error("Could not read `{path}': {error}")]
    IO {
        error: std::io::Error,
        path: PathBuf,
    },

    #[error("Could not parse `{path}': {error}")]
    Deserialize { error: String, path: PathBuf },

    #[error("Could not find post `{slug}': {error}")]
    NotFound { slug: String, error: String },
}

pub type Result<T> = std::result::Result<T, Error>;
