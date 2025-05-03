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

impl axum::response::IntoResponse for Error {
    fn into_response(self) -> axum::response::Response {
        use axum::http::StatusCode;

        let status = match &self {
            Error::IO { .. } | Error::Deserialize { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            Error::NotFound { .. } => StatusCode::NOT_FOUND,
        };

        (status, self.to_string()).into_response()
    }
}

pub type Result<T> = std::result::Result<T, Error>;

