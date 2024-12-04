use pulldown_cmark::{Event, Tag, TagEnd};
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::io::prelude::*;
use std::path::{Path, PathBuf};

use crate::store::{Error, FrontMatter, Result};

pub use pulldown_cmark::HeadingLevel;

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct Post {
    pub front_matter: FrontMatter,
    pub toc: Vec<Heading>,
    pub html_body: String,
}

#[derive(Deserialize, Serialize, Clone)]
pub struct Heading {
    // Since we capture the value of a heading as a string, it will be stripped of any formatting.
    // If we want to replicate formatting from the original heading in the TOC, I guess we'll have
    // to deal with some lifetime to capture references from the parser's events. This can be a
    // future improvement.
    pub name: String,
    #[serde(
        deserialize_with = "heading_level_from_usize",
        serialize_with = "heading_level_to_u8"
    )]
    pub level: HeadingLevel,
    pub path: [u16; HeadingLevel::H6 as usize],
}

impl std::fmt::Debug for Heading {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let section_number = self
            .path
            .iter()
            .enumerate()
            .take_while(|(i, _)| *i < (self.level as usize))
            .map(|(_, n)| format!("{}", n))
            .collect::<Vec<String>>()
            .as_slice()
            .join(".");
        write!(f, "{} {}", section_number, self.name)
    }
}

impl Heading {
    pub fn html_id(&self) -> String {
        slug::slugify(format!("{:?}", self).as_str())
    }
}

fn heading_level_from_usize<'de, D>(deserializer: D) -> std::result::Result<HeadingLevel, D::Error>
where
    D: Deserializer<'de>,
{
    let level: usize = Deserialize::deserialize(deserializer)?;
    Ok(HeadingLevel::try_from(level).map_err(|_| {
        serde::de::Error::custom(format!(
            "Expected heading level in (1, 6) but got {}",
            level
        ))
    })?)
}

fn heading_level_to_u8<S>(
    level: &HeadingLevel,
    serializer: S,
) -> std::result::Result<S::Ok, S::Error>
where
    S: Serializer,
{
    serializer.serialize_u8(*level as u8)
}

pub fn render(path: &Path) -> Result<Post> {
    let (contents, front_matter) = {
        // Even though this code should only be executed server side I am not able to pull
        // MetadataExt to allocate the String from the file size.
        //
        // let file_size = std::fs::metadata(&path)
        //     .map_err(|error| Error::IO { error, path: PathBuf::from(path) })?
        //     .size();
        // let mut buf = String::with_capacity(file_size as usize);

        let mut buf = String::new();
        let mut file = std::fs::OpenOptions::new()
            .read(true)
            .open(&path)
            .map_err(|error| Error::IO {
                error,
                path: PathBuf::from(path),
            })?;
        let front_matter = FrontMatter::read_from_file(&mut file, &path)?;
        file.read_to_string(&mut buf).map_err(|error| Error::IO {
            error,
            path: PathBuf::from(path),
        })?;
        (buf, front_matter)
    };

    let mut toc: Vec<Heading> = vec![];
    let mut heading_path = [0u16; HeadingLevel::H6 as usize]; // current section number
    let mut path_index = 0;
    let mut on_heading: Vec<pulldown_cmark::Event> = vec![];
    let all_options = pulldown_cmark::Options::all(); // does all means old footnotes style?
    let events: Vec<Event> = pulldown_cmark::Parser::new_ext(&contents, all_options)
        .into_iter()
        .map(|event| {
            match event {
                Event::Start(Tag::Heading { .. }) => {
                    assert!(on_heading.is_empty());
                    on_heading.push(event.clone());
                }
                Event::End(TagEnd::Heading(level)) => {
                    assert!(!on_heading.is_empty());
                    let name = heading_events_to_heading_name(&on_heading);
                    on_heading.clear();
                    let previous_level = toc.last().map_or(HeadingLevel::H1, |h| h.level);
                    let level_change = previous_level as i32 - level as i32;
                    if level_change < 0 {
                        path_index += level_change.abs() as usize;
                    } else if level_change > 0 {
                        for _ in 0..level_change {
                            heading_path[path_index] = 0;
                            path_index -= 1;
                        }
                    }
                    assert!(heading_path[path_index] < u16::MAX);
                    heading_path[path_index] += 1;
                    toc.push(Heading {
                        name,
                        level,
                        path: heading_path,
                    });
                }
                _ => {
                    if !on_heading.is_empty() {
                        on_heading.push(event.clone());
                    }
                }
            }
            event
        })
        .collect();
    let events = add_section_ids(events, &toc);

    // TODO: roll up toc until you just have the root heading

    // Il faut que tu vois comment correctement map/filter les événements, surtout pour générer une
    // ToC et les liens dedans. Peut-être que tu peux laisser les footnotes pour plus tard. Pas
    // besoin de faire tout le blog maintenant en vrai. Tu peux déjà commencer à rédiger. La ToC
    // sera l'occasion de faire un peu de réactivité, il y aurait plusieurs manières de la faire,
    // genre collapsible side ou topbar selon la résolution de l'écran.
    // Car c'est pas juste le blog mais aussi toute la CI, etc.

    let mut html = String::with_capacity(contents.len() * 3 / 2);
    pulldown_cmark::html::push_html(&mut html, events.into_iter());

    log::info!("ToC for \"{}\":", front_matter.metadata.title);
    for heading in toc.iter() {
        log::info!("{:?}", heading);
    }

    Ok(Post {
        front_matter,
        toc,
        html_body: html,
    })
}

fn heading_events_to_heading_name(events: &Vec<Event>) -> String {
    events
        .into_iter()
        .skip(1)
        .filter_map(|event| {
            match event {
                Event::Text(value) => Some(value),
                Event::Code(value) => Some(value),
                Event::Start(Tag::Emphasis)
                | Event::End(TagEnd::Emphasis)
                | Event::Start(Tag::Strong)
                | Event::End(TagEnd::Strong)
                | Event::Start(Tag::Strikethrough)
                | Event::End(TagEnd::Strikethrough) => None,
                _ => {
                    log::warn!("Unsupported event while collecting heading name: {event:?}");
                    None
                }
            }
            .map(|cow| &**cow)
        })
        .collect::<Vec<&str>>()
        .join(" ")
}

fn add_section_ids<'input>(events: Vec<Event<'input>>, toc: &Vec<Heading>) -> Vec<Event<'input>> {
    use pulldown_cmark::CowStr;

    let mut events_with_ids = Vec::with_capacity(events.len() + toc.len() * 2);
    let mut heading_idx = 0;
    for each in events {
        match each {
            Event::End(TagEnd::Heading(_)) => {
                let heading = &toc[heading_idx];
                heading_idx += 1;
                events_with_ids.push(Event::Text(CowStr::from(" ")));
                events_with_ids.push(Event::Html(CowStr::from(format!(
                    "<a href=\"#{}\"><span class=\"heading-anchor\">#</span></a>",
                    heading.html_id(),
                ))));
            }
            _ => (),
        }
        events_with_ids.push(each);
    }

    events_with_ids
}
