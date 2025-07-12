{
  lib,
  buildPythonPackage,
  certbot,
  fetchFromGitHub,
  hvac,
  pyopenssl,
  setuptools,
  setuptools-scm,
  zope-component,
  zope-event,
  zope-interface,
}:
buildPythonPackage {
  pname = "certbot-vault";
  version = "0.3.8";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "lopter";
    repo = "certbot-vault-plugin";
    rev = "v0.3.8-lo-patches";
    sha256 = "0ci9a0vanzv4mdi8s4ykk3nxj5swvp2hy2jibr9gb6n4ayinchg2";
  };

  build-system = [
    setuptools
    setuptools-scm
  ];

  dependencies = [
    certbot
    hvac
    pyopenssl
    zope-component
    zope-event
    zope-interface
  ];

  meta = with lib; {
    homepage = "https://github.com/lopter/certbot-vault-plugin";
    description = "Plugin for Certbot to store certificates in HashiCorp Vault";
    licenses = licenses.mit;
    maintainers = [ ];
  };
}
