{
  buildPythonPackage,
  fetchPypi,
  lib,
  setuptools,
  types-requests,
  ...
}:
buildPythonPackage rec {
  pname = "types-hvac";
  version = "2.4.0.20251115";

  src = fetchPypi {
    pname = "types_hvac";
    inherit version;
    sha256 = "a7b5d0e86961e4d7f07e51b60b2eedcac5f8db8b98b031d4a4b716215c21df3a";
  };

  pyproject = true;
  build-system = [ setuptools ];

  dependencies = [ types-requests ];

  doCheck = false;

  meta = {
    homepage = "https://github.com/hvac/hvac";
    description = "Typing stubs for hvac";
    license = lib.licenses.asl20;
  };
}
