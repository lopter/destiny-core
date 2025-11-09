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

  # update this can you load it from local disk
  # so you don't have to push/pull from github?
  src = fetchFromGitHub {
    owner = "lopter";
    repo = "certbot-vault-plugin";
    rev = "v0.3.8-lo-patches";
    sha256 = "U98ANm5YlNH4UDbPU1uvg1861N31hvb3GfAhx2zZfWM=";
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
