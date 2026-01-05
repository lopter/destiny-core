{ self, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      mkBackups =
        ps:
        ps.buildPythonPackage {
          pname = "backups";
          version = "0.0.1";
          src = ./.;
          pyproject = true;

          build-system = [ ps.setuptools ];

          dependencies = with ps; [
            click
            hvac
            pydantic
            requests
          ];

          nativeCheckInputs = [
            pkgs.openbao

            ps.pytest
            # ps.types-hvac
            ps.types-requests
          ];

          propagatedBuildInputs = with pkgs; [
            gzip
            restic
            rsync
            util-linux # findmnt
          ];
        };
      pythonPkgs = pkgs.python3Packages;
      backups = mkBackups pythonPkgs;
    in
    {
      apps.backups-dump.type = "app";
      apps.backups-dump.program = "${backups}/bin/clan-destiny-backups-dump";

      apps.backups-restore.type = "app";
      apps.backups-restore.program = "${backups}/bin/clan-destiny-backups-restore";

      checks = {
        rsync-dump-restore = pkgs.testers.runNixOSTest (
          let
            inherit (self.inputs) nixpkgs;
            snakeoilCerts = nixpkgs + "/nixos/tests/common/acme/server/snakeoil-certs.nix";
            certs = import snakeoilCerts;
            openBaoDomain = certs.domain;
            sshCA =
              pkgs.runCommandLocal "generate-ssh-ca"
                {
                  buildInputs = [
                    pkgs.coreutils
                    pkgs.openssh
                  ];
                }
                ''
                  mkdir $out
                  ssh-keygen -t ed25519 -N "" -C "Test SSH CA" -f $out/ssh-ca
                '';
          in
          {
            name = "rsync-dump-restore";

            interactive.sshBackdoor.enable = true;

            # NOTE: IP adresses seem to be handed out from 192.168.0.0/24
            # in ascending order to the nodes sorted alphabetically:
            nodes =
              let
                siteConfig = {
                  security.pki.certificateFiles = [ certs.ca.cert ];

                  networking.extraHosts = ''
                    192.168.1.1 ${openBaoDomain}
                  '';

                  services.openssh = {
                    enable = true;
                    hostKeys = [
                      {
                        path = "/etc/ssh/ssh_host_ed25519_key";
                        type = "ed25519";
                      }
                    ];
                    settings = {
                      PasswordAuthentication = false;
                      KbdInteractiveAuthentication = false;
                      PermitRootLogin = "yes";
                      TrustedUserCAKeys = sshCA + "/ssh-ca.pub";
                    };
                  };

                  environment.systemPackages = [
                    backups
                    pkgs.jq
                    pkgs.openssh
                    (pkgs.python3.withPackages (ps: [
                      ps.ipython
                      (mkBackups ps)
                    ]))
                  ];

                  users.users.root.openssh.authorizedKeys.keys = [
                    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCy5x25/e1NxUeELoWXFqHvavS1GgXYmXI59oTpGli/LFyR3IME9e1CA/dJtrxMxl2fiNut5FLV3Tba79IaqgwdaeOKZz7phCw/QQNhr50kJhdEzlXIAGK5a2m2iD9oIWbCcKXh+CENwqHlvB/4cMelX/WXfDexcIEDeCovnWTll3L3EkD9b4CdN04EljRmRRfuie067poiIIPKoNN55F3XHnFNujQq6HPHN2HSo0uHYfObP8ZrclqCKutyV5qiegM4G3VN50EiWBMwJPeXVK7/BcovfZGLNE49G5Re+ruLcWTCmCrQ2bStAmuIEaiJ+BBAqfJtFTUN/fIrl4pyJStjAsQNELegQ5sEKHwfg/1TN1Zl2I3NumRdvPNpOzJCedwWC6hrOFrQMHgnp+4Wrw18oMZpDKM1fIdBi6uSDHAgAaWWpZNA/+xC9Ap6uQ2GbYTTcNaF0UGBPktj9DOJYWPF/Zm3gJ0aVE3GL9yUkaa+rWRThJTa4Xvuv5eNSFYD3qNUu5gdvu0VeyMtQ3fsy050Qf1UPDIwTxvK1LvLF+0MWfQtDGADggf7rmMc0rBc+kNAoklC1j5zjHh9eyvsZr9QImxesKL+e55xIrW4MQaBJh+eyKGjT7DgYVTiPMW1Vygn/uXfD7Ezbj18GhOFvWFe+jqRc2qkBOi10zOgUHrI6Q=="
                  ];
                };
              in
              {
                openBaoSSHCa =
                  { config, ... }:
                  {
                    security.pki.certificateFiles = [ certs.ca.cert ];

                    networking.extraHosts = ''
                      127.0.0.1 ${openBaoDomain}
                    '';

                    services.openbao = {
                      enable = true;
                      settings = {
                        listener.default = {
                          type = "tcp";
                          address = "0.0.0.0:8200";
                          tls_cert_file = certs.${openBaoDomain}.cert;
                          tls_key_file = certs.${openBaoDomain}.key;
                        };
                        cluster_addr = "https://127.0.0.1:8201";
                        api_addr = "https://${openBaoDomain}:8200";
                        storage.raft.path = "/var/lib/openbao";
                      };
                    };

                    environment.variables = {
                      BAO_ADDR = config.services.openbao.settings.api_addr;
                      BAO_FORMAT = "json";
                    };

                    networking.firewall.allowedTCPPorts = [ 8200 ];
                  };

                siteA = siteConfig;
                siteB = siteConfig;
              };

            testScript = # python
              ''
                import json
                import textwrap

                ENGINE_PATH = "ssh-backups-ca"
                SIGNER_ROLE = "backups-dump"
                APPROLE_NAME = "backup-client"
                POLICY_NAME = "backup-ssh-signer"
                BAO_ADDR = "https://${openBaoDomain}:8200"

                HOST_KEY = "/etc/ssh/ssh_host_ed25519_key"
                HOST_KEY_PUB = "/etc/ssh/ssh_host_ed25519_key.pub"

                start_all()

                #
                # Initialize OpenBao
                #
                with subtest("Wait for OpenBao to start"):
                    openBaoSSHCa.wait_for_unit("openbao.service")
                    openBaoSSHCa.wait_for_open_port(8200)

                with subtest("Initialize OpenBao"):
                    init_output = json.loads(
                        openBaoSSHCa.succeed("bao operator init")
                    )

                with subtest("Unseal OpenBao"):
                    threshold = init_output["unseal_threshold"]
                    for key in init_output["unseal_keys_b64"][:threshold]:
                        openBaoSSHCa.succeed(f"bao operator unseal {key}")

                with subtest("Login with root token"):
                    root_token = init_output["root_token"]
                    openBaoSSHCa.succeed(f"bao login {root_token}")

                #
                # Configure SSH secrets engine
                #
                with subtest("Enable SSH secrets engine"):
                    openBaoSSHCa.succeed(
                        f"bao secrets enable -path {ENGINE_PATH} ssh"
                    )

                with subtest("Generate and configure SSH CA keypair"):
                    openBaoSSHCa.succeed(textwrap.dedent(f"""
                        bao write {ENGINE_PATH}/config/ca \\
                          private_key=@${sshCA}/ssh-ca \\
                          public_key=@${sshCA}/ssh-ca.pub
                    """))

                with subtest("Configure signer role"):
                    role_config = json.dumps({
                        "default_user": "root",
                        "key_type": "ca",
                        "allowed_users": "root",
                        "ttl": "1h",
                        "max_ttl": "24h",
                        "allow_user_certificates": True,
                        "allow_user_key_ids": True,
                        "default_extensions": {},
                        "default_critical_options": {},
                        "allowed_critical_options": "force-command",
                    })
                    openBaoSSHCa.succeed(textwrap.dedent(f"""
                       bao write {ENGINE_PATH}/roles/{SIGNER_ROLE} - <<'EOF'
                       {role_config}
                       EOF
                    """))

                #
                # Configure AppRole authentication
                #
                with subtest("Enable AppRole auth and create policy"):
                    openBaoSSHCa.succeed("bao auth enable approle")
                    openBaoSSHCa.succeed(textwrap.dedent(f"""
                        bao policy write {POLICY_NAME} - <<'EOF'
                        path "ssh-backups-ca/sign/backups-dump" {{
                            capabilities = ["create", "update"]
                        }}
                        EOF
                    """))
                    openBaoSSHCa.succeed(textwrap.dedent(f"""
                        bao write auth/approle/role/{APPROLE_NAME} \\
                          policies={POLICY_NAME} \\
                          token_ttl=1h token_max_ttl=4h
                    """))

                with subtest("Get AppRole credentials"):
                    role_id_out = json.loads(openBaoSSHCa.succeed(
                        f"bao read auth/approle/role/{APPROLE_NAME}/role-id"
                    ))
                    role_id = role_id_out["data"]["role_id"]

                    secret_id_out = json.loads(openBaoSSHCa.succeed(
                        f"bao write -f auth/approle/role/{APPROLE_NAME}/secret-id"
                    ))
                    secret_id = secret_id_out["data"]["secret_id"]

                #
                # Setup AppRole credentials on sites using machine identity
                #
                with subtest("Setup credentials on siteA"):
                    siteA.succeed(f"echo '{role_id}' > /etc/openbao-role-id")
                    siteA.succeed(f"echo '{secret_id}' > /etc/openbao-secret-id")
                    siteA.succeed("chmod 600 /etc/openbao-*")

                with subtest("Setup credentials on siteB"):
                    siteB.succeed(f"echo '{role_id}' > /etc/openbao-role-id")
                    siteB.succeed(f"echo '{secret_id}' > /etc/openbao-secret-id")
                    siteB.succeed("chmod 600 /etc/openbao-*")

                #
                # Create test data
                #
                with subtest("Create test data on siteA"):
                    siteA.succeed("mkdir -p /data/source")
                    siteA.succeed(textwrap.dedent("""
                          echo 'test file content' > /data/source/file1.txt
                    """))
                    siteA.succeed("echo 'another file' > /data/source/file2.txt")
                    siteA.succeed("mkdir -p /data/source/subdir")
                    siteA.succeed(textwrap.dedent("""
                        echo 'nested' > /data/source/subdir/nested.txt
                    """))

                with subtest("Create backup destination on siteB"):
                    siteB.succeed("mkdir -p /data/backup-from-a")

                #
                # Test PULL: siteB pulls from siteA
                #
                with subtest("Test pull backup: siteB pulls from siteA"):
                    pull_config = json.dumps({
                        "jobsByName": {
                            "pull-from-a": {
                                "type": "rsync",
                                "direction": "pull",
                                "localHost": "siteB",
                                "localPath": "/data/backup-from-a/",
                                "remoteHost": "siteA",
                                "remotePath": "/data/source/",
                                "oneFileSystem": False,
                            }
                        },
                        "ssh": {
                            "publicKeyPath": HOST_KEY_PUB,
                            "privateKeyPath": HOST_KEY,
                            "ca": {
                                "addr": BAO_ADDR,
                                "roleIdPath": "/etc/openbao-role-id",
                                "secretIdPath": "/etc/openbao-secret-id",
                                "tlsServerName": "${openBaoDomain}",
                                "enginePath": ENGINE_PATH,
                                "signerRole": SIGNER_ROLE,
                            }
                        }
                    })
                    siteB.succeed(textwrap.dedent(f"""
                      cat > /etc/backups-pull.json <<'EOF'
                      {pull_config}
                      EOF
                    """))

                    # Add siteA to known_hosts
                    siteB.succeed(
                        "ssh-keyscan -H siteA >> /root/.ssh/known_hosts 2>/dev/null"
                    )

                    # Run the backup
                    siteB.succeed(
                        "clan-destiny-backups-dump -c /etc/backups-pull.json run"
                    )

                with subtest("Verify pull backup data"):
                    result = siteB.succeed("cat /data/backup-from-a/file1.txt")
                    assert "test file content" in result

                    result = siteB.succeed(
                        "cat /data/backup-from-a/subdir/nested.txt"
                    )
                    assert "nested" in result

                #
                # Test PUSH: siteA pushes to siteB
                #
                with subtest("Test push backup: siteA pushes to siteB"):
                    push_config = json.dumps({
                        "jobsByName": {
                            "push-to-b": {
                                "type": "rsync",
                                "direction": "push",
                                "localHost": "siteA",
                                "localPath": "/data/source/",
                                "remoteHost": "siteB",
                                "remotePath": "/data/pushed-from-a/",
                                "oneFileSystem": False,
                            }
                        },
                        "ssh": {
                            "publicKeyPath": HOST_KEY_PUB,
                            "privateKeyPath": HOST_KEY,
                            "ca": {
                                "addr": BAO_ADDR,
                                "roleIdPath": "/etc/openbao-role-id",
                                "secretIdPath": "/etc/openbao-secret-id",
                                "tlsServerName": "${openBaoDomain}",
                                "enginePath": ENGINE_PATH,
                                "signerRole": SIGNER_ROLE,
                            }
                        }
                    })
                    siteA.succeed(textwrap.dedent(f"""
                        cat > /etc/backups-push.json <<'EOF'
                        {push_config}
                        EOF
                    """))

                    # Create destination on siteB
                    siteB.succeed("mkdir -p /data/pushed-from-a")

                    # Add siteB to known_hosts
                    siteA.succeed(
                        "ssh-keyscan -H siteB >> /root/.ssh/known_hosts 2>/dev/null"
                    )

                    # Run the backup
                    siteA.succeed(
                        "clan-destiny-backups-dump -c /etc/backups-push.json run"
                    )

                with subtest("Verify push backup data"):
                    result = siteB.succeed("cat /data/pushed-from-a/file1.txt")
                    assert "test file content" in result

                    result = siteB.succeed(
                        "cat /data/pushed-from-a/subdir/nested.txt"
                    )
                    assert "nested" in result
              '';
          }
        );
      };

      devShells.backups = pkgs.mkShell {
        propagatedBuildInputs = [
          pythonPkgs.ipython
          pythonPkgs.mypy

          backups.nativeBuildInputs
          backups.propagatedBuildInputs
        ];
      };

      packages.backups = backups;
    };
}
