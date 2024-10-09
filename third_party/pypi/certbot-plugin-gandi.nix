{ lib
, buildPythonPackage
, certbot
, fetchPypi
, requests
, zope_interface
}:
buildPythonPackage rec {
  pname = "certbot-plugin-gandi";
  version = "1.5.0";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-xiDkCi6oKCG/UB61QY9TtTnOLVyouQBavYyjmzqdIkA=";
  };

  propagatedBuildInputs = [ certbot requests zope_interface ];

  meta = with lib; {
    homepage = "https://github.com/obynio/certbot-plugin-gandi";
    description = "Plugin for Certbot that uses the Gandi LiveDNS API to allow Gandi customers to prove control of a domain name.";
    licenses = licenses.mit;
    maintainers = with maintainers; [ ];
  };
}
