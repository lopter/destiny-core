{
  buildPythonPackage,
  certbot,
  fetchFromGitHub,
  hatchling,
  lib,
  requests,
  zope_interface,
}:
buildPythonPackage rec {
  pname = "certbot-plugin-gandi";
  version = "1.6.1";
  pyproject = true;

  src = fetchFromGitHub {
    rev = "dd4fb4c8b851c36ccbb29c982ddc407f0a12844d";
    owner = "lopter";
    # louis@(2025-07-12): Note: project will like change repo:
    #
    # > In order to match the naming convention for certbot plugin, the plugin has
    # > been repackaged under a new name certbot-dns-plugin and legacy owner of
    # > the previous package will receive the new package as a dependency.
    repo = pname;
    sha256 = "sha256-s0SEuYU14buovJzky5ZCIPbsaIW42SfXJov220LFnd0=";
  };

  build-system = [
    hatchling
  ];

  dependencies = [
    certbot
    requests
    zope_interface
  ];

  meta = with lib; {
    homepage = "https://github.com/obynio/certbot-plugin-gandi";
    description = "Plugin for Certbot that uses the Gandi LiveDNS API to allow Gandi customers to prove control of a domain name.";
    licenses = licenses.mit;
    maintainers = [ ];
  };
}
