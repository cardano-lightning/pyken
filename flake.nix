{
  description = "CL signatures experiments";
  nixConfig = {
    bash-prompt = ''\[\033[1;32m\][cl-sig:\w]\$\[\033[0m\] '';
  };

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    git-hooks-nix.url = "github:cachix/git-hooks.nix";
    git-hooks-nix.inputs.nixpkgs.follows = "nixpkgs";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";
    aiken.url = "github:aiken-lang/aiken/94ff20253b3d43ee5fcf501bb13902f58c729791";
    rust-overlay.url = "github:oxalica/rust-overlay";
  };

  outputs = inputs @ {flake-parts, ...}:
    flake-parts.lib.mkFlake {inherit inputs;}
    {
      imports = [
        inputs.git-hooks-nix.flakeModule
        inputs.treefmt-nix.flakeModule
      ];
      systems = ["x86_64-linux" "aarch64-darwin"];
      perSystem = {
        config,
        self',
        inputs',
        pkgs,
        system,
        ...
      }: let
        pkgs = import inputs.nixpkgs {
          inherit system;
          overlays = [
            (import inputs.rust-overlay)
            (final: prev: let
              version = "1.3.3";
            in {
              python311Packages = prev.python311Packages.override {
                overrides = pyFinal: pyPrev: {
                  frozenlist = pyPrev.frozenlist.overridePythonAttrs (old: {
                    version = version;
                    # Using the same approach as the original derivation:
                    src = final.fetchFromGitHub {
                      owner = "aio-libs";
                      repo = "frozenlist";
                      tag = "v${version}";
                      # Replace with the sha you got from nix-prefetch-url
                      hash = "sha256-lJWRdXvuzyvJwNSpv0+ojY4rwws3jwDtlLOqYyLPrZc=";
                    };

                    # Optionally keep or remove the existing `postPatch` etc.
                    # e.g. remove `rm pytest.ini` if 1.3.3 doesn't have it
                  });
                };
              };
            })
          ];
        };

        makeRustInfo = {
          version,
          profile,
        }: let
          rust = pkgs.rust-bin.${version}.latest.${profile}.override {extensions = ["rust-src"];};
        in {
          name = "rust-" + version + "-" + profile;

          # From https://discourse.nixos.org/t/rust-src-not-found-and-other-misadventures-of-developing-rust-on-nixos/11570/11
          path = "${rust}/lib/rustlib/src/rust/library";

          drvs = [
            pkgs.just
            pkgs.pkg-config
            pkgs.rust-analyzer
            # pkgs.rustup
            pkgs.cargo-watch
            rust
          ];
        };

        makeRustEnv = {
          version,
          profile,
        }: let
          rustInfo = makeRustInfo {
            inherit version profile;
          };
        in
          pkgs.buildEnv {
            name = rustInfo.name;
            paths = rustInfo.drvs;
          };

        matrix = {
          stable-default = {
            version = "stable";
            profile = "default";
          };

          stable-minimal = {
            version = "stable";
            profile = "minimal";
          };

          beta-default = {
            version = "beta";
            profile = "default";
          };

          beta-minimal = {
            version = "beta";
            profile = "minimal";
          };
        };
      in {
        treefmt = {
          projectRootFile = "flake.nix";
          flakeFormatter = true;
          programs = {
            prettier = {
              enable = true;
              settings = {
                printWidth = 80;
                proseWrap = "always";
              };
            };
            alejandra.enable = true;
          };
        };
        pre-commit.settings.hooks = {
          treefmt.enable = true;
          aiken = {
            enable = true;
            name = "aiken";
            description = "Run aiken's formatter on ./aik";
            files = "\\.ak";
            entry = "${inputs'.aiken.packages.aiken}/bin/aiken fmt ./aik";
          };
        };

        devShells.default = let
          version = matrix.stable-default.version;
          profile = matrix.stable-default.profile;
          rustInfo = makeRustInfo {
            inherit version profile;
          };
          lib-path = pkgs.lib.makeLibraryPath [
            pkgs.openssl
          ];
        in
          pkgs.mkShell {
            RUST_SRC_PATH = rustInfo.path;
            buildInputs = rustInfo.drvs;
            nativeBuildInputs = [
              config.treefmt.build.wrapper
              pkgs.openssl.dev
            ];
            shellHook = ''
              ${config.pre-commit.installationScript}
              echo 1>&2 "Welcome to the development shell!"

              SOURCE_DATE_EPOCH=$(date +%s)
              export "LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${lib-path}"
              VENV=.venv
              if [ ! -d $VENV ]; then
                python -m venv $VENV
                source ./$VENV/bin/activate
                pip install --upgrade pip
                pip install -r requirements.txt
              fi
              source ./$VENV/bin/activate
              export PYTHONPATH=`pwd`/$VENV/${pkgs.python311.sitePackages}/:$PYTHONPATH
            '';
            postShellHook = ''
              mkdir -p $VENV/lib/python311.12/site-packages
              ln -sf ${pkgs.python311.sitePackages}/* $VENV/lib/python311.12/site-packages
            '';
            name = "cardano-lightning";
            packages = [
              inputs'.aiken.packages.aiken
              pkgs.bun
              pkgs.deno
              pkgs.nodejs
              pkgs.python311Packages.frozenlist
              pkgs.python311
            ];
          };
      };
      flake = {};
    };
}
