use anyhow::{Context, Result};

pub fn main() -> Result<()> {
    let username =
        std::env::var("username").context("Could not find username in the environment")?;
    let password =
        std::env::var("password").context("Could not find password in the environment")?;
    let mut client = pam::Client::with_password("hass-pam-authenticate")
        .context("Could not create PAM client for service `hass-pam-authenticate`")?;
    client
        .conversation_mut()
        .set_credentials(username.clone(), password);
    client
        .authenticate()
        .with_context(|| format!("Could not authenticate user `{}`", username))?;
    Ok(())
}
