{
  # To update images, install and use nix-prefetch-docker, e.g.:
  #
  # nix-prefetch-docker --image-name debian --image-tag bullseye --arch amd64
  alpineDetailsBySystem = {
    x86_64-linux = {
      imageName = "amd64/alpine";
      imageDigest = "sha256:48d9183eb12a05c99bcc0bf44a003607b8e941e1d4f41f9ad12bdcc4b5672f86";
      sha256 = "sha256-XfnogxDJPYwyDQWqz7vyxfJoaam0DSTcwwTvq4aZC/8=";
      finalImageName = "amd64/alpine";
      finalImageTag = "3.18.4";
    };
    armv6l-linux = {
      imageName = "arm32v6/alpine";
      imageDigest = "sha256:777e2106170c66742ddbe77f703badb7dc94d9a5b1dc2c4a01538fad9aef56bb";
      sha256 = "sha256-gxcOeft00YleYOw3CZAAeY0nHSqT9PVeJHqH464TPok=";
      finalImageName = "arm32v6/alpine";
      finalImageTag = "3.18.4";
    };
  };
}
