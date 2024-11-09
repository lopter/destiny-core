{
  lib,
  buildPythonPackage,
  certbot,
  fetchFromGitHub,
  hvac,
  pyopenssl,
  zope_interface,
}:
buildPythonPackage rec {
  pname = "certbot-vault";
  version = "0.3.8";

  src = fetchFromGitHub {
    owner = "lopter";
    repo = "certbot-vault-plugin";
    rev = "v0.3.8-lo-patches";
    sha256 = "0ci9a0vanzv4mdi8s4ykk3nxj5swvp2hy2jibr9gb6n4ayinchg2";
  };

  propagatedBuildInputs = [
    certbot
    hvac
    pyopenssl
    zope_interface
  ];

  meta = with lib; {
    homepage = "https://github.com/lopter/certbot-vault-plugin";
    description = "Plugin for Certbot to store certificates in HashiCorp Vault";
    licenses = licenses.mit;
    maintainers = with maintainers; [ ];
  };
}
