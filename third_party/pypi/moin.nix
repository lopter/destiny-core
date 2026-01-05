{
  buildPythonPackage,
}:
buildPythonPackage {
  pname = "moin";
  version = "1.9.11";

  format = "setuptools";

  src = builtins.fetchTarball {
    url = "https://github.com/moinwiki/moin-1.9/releases/download/1.9.11/moin-1.9.11.tar.gz";
    sha256 = "0lrncrmg2bl7mvk3i9qyq69i0agxq8cg90p51w6jnax6ljjlpx58";
  };
}
