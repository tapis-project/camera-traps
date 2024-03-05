{
  description = "Image Scoring plugin for Camera Traps packaged using poetry2nix";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.poetry2nix = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };
  inputs.shell-utils.url = "github:waltermoreira/shell-utils";

  outputs = { self, nixpkgs, flake-utils, poetry2nix, shell-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # see https://github.com/nix-community/poetry2nix/tree/master#api for more functions and examples.
        inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication mkPoetryEnv;

        # Standard nix packages
        pkgs = nixpkgs.legacyPackages.${system};
        # Shell utilities used for creating the dev shell
        shell = shell-utils.myShell.${system};

        # Initial Python 3.8 instance that will be used to create several Python packages.
        myPython = pkgs.python38;

        # The score plugin depends on a number of git repositories hosted in GitHub.
        # NOTE: These packages are NOT specified in the Poetry requirements (pyproject.toml) for
        #     the appluition.
        # The strategy used is to clone each of those repositories into the Nix store and build
        # them as a python package, using the myPython (Python 3.8) instance defined above.
        #
        # ai4eutils repo ----
        ai4eutils = myPython.pkgs.buildPythonPackage {
          name = "ai4eutils";
          src = pkgs.fetchgit {
            url = "https://github.com/microsoft/ai4eutils";
            rev = "a7aefc9cf6ff0564a83e0a1ddc903ef22561fdd5";
            sha256 = "sha256-w1Eid+0exFzQobLjC3Eh1UlvLgauw/FY5H4LsnER3ek=";
          };
          format = "other";
          installPhase = ''
            mkdir -p $out/lib/python3.8/site-packages/ai4eutils
            cp -r . $out/lib/python3.8/site-packages/ai4eutils/
          '';
        };

        # cameratrapsMD repo ----
        cameraTrapsMD = myPython.pkgs.buildPythonPackage {
          name = "camera_traps_MD";
          src = pkgs.fetchFromGitHub {
            owner = "sowbaranika1302";
            repo = "camera_traps_MD";
            rev = "28f91e01b2afadde23a0e653a4ab9d6879a976c9";
            hash = "sha256-VBwprg1qvxtWBMOZpmJk6qqUhXUvmnVNqEvgoES4J5k=";
          };
          format = "other";
          installPhase = ''
            mkdir -p $out/lib/python3.8/site-packages/camera_traps_MD
            cp -r . $out/lib/python3.8/site-packages/camera_traps_MD/
          '';
        };

        # yolov5 repo -----
        yolov5 = myPython.pkgs.buildPythonPackage {
          name = "yolov5";
          src = pkgs.fetchFromGitHub {
            owner = "ultralytics";
            repo = "yolov5";
            rev = "c23a441c9df7ca9b1f275e8c8719c949269160d1";
            hash = "sha256-YbedVzBResnU5lwlxYkMkjqJ0f1Q48FZs+tIS1a1MUk=";
          };
          format = "other";
          installPhase = ''
            mkdir -p $out/lib/python3.8/site-packages/yolov5
            cp -r . $out/lib/python3.8/site-packages/yolov5/
          '';
        };

        ctevents =
          let mySrc = pkgs.fetchFromGitHub {
            owner = "tapis-project";
            repo = "camera-traps";
            rev = "423ba3884d358b2716cd9a7da450d7a5df0f925a";
            hash = "sha256-QaHQ2Bfuyz8+Qesp7bWZ1vEA7dIJUj60NqSub7QoKFo=";
          };
          in
          mkPoetryApplication {
            python = myPython;
            projectDir = "${mySrc}/src/python";
            preferWheels = true;
          };

        # The score plugin also depends on a release of the Microsoft MegaDetector model.
        # Fetch the MegaDetector PyTorch model release (.pt) file
        mdPtModel = pkgs.fetchurl {
          url = "https://github.com/microsoft/CameraTraps/releases/download/v5.0/md_v5a.0.0.pt";
          sha256 = "0xmj04xwvvpqfhpvxp0j8gbkkmi98zvb8k6cs3iz4l40gklqzs4l";
        };
        # Ensure that the model file has the name expected by the score plugin (md_v5a.0.0.pt)
        ptModelDir = pkgs.stdenv.mkDerivation {
          name = "ptModelDir";
          src = self;
          dontBuild = true;
          installPhase = ''
            mkdir -p $out;
            cp ${mdPtModel} $out/md_v5a.0.0.pt
          '';
        };

        exampleImages = pkgs.stdenv.mkDerivation {
          name = "example_images";
          src = ./example_images;
          installPhase = ''
            mkdir -p $out
            cp * $out
          '';
        };

        app = { kind, name }:
          let
            # Make a Python package with the Score Plugin source code and third-party dependencies 
            # defined in the pyproject.toml file using the mkPoetryApplication function
            # `kind` can be
            # mkPoetryEnv: to build a Python interpreter with the right environment, or
            # mkPoetryApplication: to build the actual executable
            poetryApp = kind {
              python = myPython;
              projectDir = ./.;
              preferWheels = true;
            };
          in
          # Bring everything together using a custom derivation. The approach is to wrap myApp
            # with a shell script which calls the myApp binary (${myApp}/bin/image_scoring_plugin) after 
            # doing the following:
            #   1. changes to the directory containing the model.pt file.
            #   2. sets the python path to include paths to the git repos installed above
            # Note that 1) is needed because the score plugin code makes implicit assumption that
            # pt model file is in the current working directory. 
          pkgs.stdenv.mkDerivation {
            inherit name;
            buildInputs = [ pkgs.makeWrapper ptModelDir ];
            src = self;
            dontBuild = true;
            installPhase = ''
              makeWrapper ${poetryApp}/bin/${name} $out/bin/${name} \
              --chdir ${ptModelDir} \
              --set IMAGES_DIR_PATH ${exampleImages} \
              --set OUTPUT_DIR_PATH /tmp \
              --set PYTHONPATH \
              "${cameraTrapsMD}/lib/python3.8/site-packages:\
              ${cameraTrapsMD}/lib/python3.8/site-packages/camera_traps_MD:\
              ${ai4eutils}/lib/python3.8/site-packages/ai4eutils:\
              ${yolov5}/lib/python3.8/site-packages/yolov5:\
              ${ctevents}/lib/python3.8/site-packages"
            '';
          };

        # Put together the environment and the executable
        fullApp = pkgs.symlinkJoin {
          name = "image_scoring_plugin";
          paths = [
            (app
              { kind = mkPoetryEnv; name = "python"; })
            (app
              { kind = mkPoetryApplication; name = "image_scoring_plugin"; })
          ];
        };
      in
      rec {
        packages = {
          # set the wrapped app package to the default package
          default = fullApp;
        };

        devShells.default = shell {
          packages = [ poetry2nix.packages.${system}.poetry fullApp ];
        };
      });
}
