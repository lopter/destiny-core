{
  buildPythonPackage,
  certbot,
  fetchFromGitHub,
  hatchling,
  lib,
  requests,
  zope-interface,
}:
buildPythonPackage rec {
  pname = "certbot-plugin-gandi";
  version = "1.6.1";
  pyproject = true;

  src = fetchFromGitHub {
    rev = "52f4d2a5a9e1fc3382c0291b81e44317017d6c0d";
    owner = "lopter";
    # louis@(2025-07-12): Note: project will like change repo:
    #
    # > In order to match the naming convention for certbot plugin, the plugin has
    # > been repackaged under a new name certbot-dns-plugin and legacy owner of
    # > the previous package will receive the new package as a dependency.
    repo = pname;
    sha256 = "sha256-xrmAaqgoq2LES9iL21uH3l8tIP5xs9t1bHyQ/XybL80=";
  };

  build-system = [
    hatchling
  ];

  dependencies = [
    certbot
    requests
    zope-interface
  ];

  meta = with lib; {
    homepage = "https://github.com/obynio/certbot-plugin-gandi";
    description = "Plugin for Certbot that uses the Gandi LiveDNS API to allow Gandi customers to prove control of a domain name.";
    licenses = licenses.mit;
    maintainers = [ ];
  };
}
