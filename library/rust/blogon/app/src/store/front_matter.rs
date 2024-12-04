use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::io::prelude::*;
use std::path::{Path, PathBuf};

use crate::store::{Error, Result};

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct FrontMatter {
    pub slug: String,
    pub metadata: Metadata,
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct Metadata {
    #[serde(
        deserialize_with = "naive_date_from_str",
        serialize_with = "naive_date_to_str"
    )]
    pub date: Option<chrono::NaiveDate>,
    pub tags: Vec<String>,
    pub title: String,
}

fn naive_date_from_str<'de, D>(
    deserializer: D,
) -> std::result::Result<Option<chrono::NaiveDate>, D::Error>
where
    D: Deserializer<'de>,
{
    let s: String = Deserialize::deserialize(deserializer)?;
    if s == "null" {
        return Ok(None);
    }
    Ok(Some(
        chrono::NaiveDate::parse_from_str(&s, "%Y-%m-%d").map_err(serde::de::Error::custom)?,
    ))
}

fn naive_date_to_str<S>(
    dt: &Option<chrono::NaiveDate>,
    serializer: S,
) -> std::result::Result<S::Ok, S::Error>
where
    S: Serializer,
{
    let s = match dt {
        Some(v) => v.format("%Y-%m-%d").to_string(),
        None => String::from("null"),
    };
    serializer.serialize_str(s.as_str())
}

impl FrontMatter {
    /// Extract the front matter and deserialize with yaml.
    /// The file cursor is moved after the front matter.
    pub fn read(path: &Path) -> Result<Self> {
        let mut file = std::fs::OpenOptions::new()
            .read(true)
            .open(&path)
            .map_err(|error| Error::IO {
                error,
                path: PathBuf::from(path),
            })?;

        Self::read_from_file(&mut file, path)
    }

    pub fn read_from_file(file: &mut std::fs::File, path: &Path) -> Result<Self> {
        // While this is ugly and fragile, it's light on memory allocations, and does
        // not pull something like the regex crate which would grow the WASM by a lot:
        let mut front_matter_start: i32 = -1;
        let mut front_matter_size = 0;
        let mut hyphens = 0;
        let mut spaces = 0;
        let boundary_size = "---\n".len();
        while front_matter_size == 0 {
            let mut buf = [0; 1024];
            let nbytes = file.read(&mut buf[..]).map_err(|error| Error::IO {
                error,
                path: PathBuf::from(path),
            })?;
            if nbytes == 0 {
                break;
            }
            let mut i = 0;
            while i < nbytes && front_matter_size == 0 {
                while i + hyphens < nbytes && buf[i + hyphens] == b'-' {
                    hyphens += 1;
                }
                if i + hyphens == nbytes {
                    continue; // grab a new buffer
                }
                i += hyphens;
                if hyphens == 3 {
                    // skip whitespace and try to find a newline
                    while i + spaces < nbytes
                        && (buf[i + spaces] == b' ' || buf[i + spaces] == b'\t')
                    {
                        spaces += 1;
                    }
                    if i + spaces == nbytes {
                        continue; // grab a new buffer
                    }
                    i += spaces;
                    if buf[i] == b'\n' {
                        i += 1;
                        if front_matter_start < 0 {
                            front_matter_start =
                                i32::try_from(i).map_err(|_| Error::Deserialize {
                                    error: String::from("integer overflow"),
                                    path: PathBuf::from(path),
                                })?;
                        } else {
                            front_matter_size = i - front_matter_start as usize - boundary_size;
                        }
                    }
                    spaces = 0;
                }
                hyphens = 0;
                // skip and try to find a newline
                while i < nbytes && buf[i] != b'\n' {
                    i += 1;
                }
                if i < nbytes && buf[i] == b'\n' {
                    i += 1; // skip new line
                }
            }
        }
        if front_matter_start == -1 || front_matter_size == 0 {
            return Err(Error::Deserialize {
                error: String::from("front matter is missing"),
                path: PathBuf::from(path),
            });
        }

        // Read the ending boundary so that we don't have to seek over it:
        let mut buf = vec![0; front_matter_size + boundary_size];
        let offset = std::io::SeekFrom::Start(front_matter_start as u64);
        file.seek(offset).map_err(|error| Error::IO {
            error,
            path: PathBuf::from(path),
        })?;
        file.read_exact(buf.as_mut_slice())
            .map_err(|error| Error::IO {
                error,
                path: PathBuf::from(path),
            })?;

        let front_matter =
            std::str::from_utf8(&buf.as_slice()[..front_matter_size]).map_err(|_| {
                Error::Deserialize {
                    error: String::from("invalid utf-8"),
                    path: PathBuf::from(path),
                }
            })?;
        let metadata =
            serde_yml::de::from_str(front_matter).map_err(|error| Error::Deserialize {
                error: format!("front matter is not valid YAML: {}", error.to_string()),
                path: PathBuf::from(path),
            })?;

        let file_stem = path.file_stem().unwrap().to_str().unwrap();

        Ok(Self {
            slug: slug::slugify(file_stem),
            metadata,
        })
    }
}
