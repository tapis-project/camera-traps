{
  description = "Image Generating plugin for Camera Traps packaged using poetry2nix";

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

        # Initial Python 3.10 instance that will be used for the Image Generating plugin.
        myPython = pkgs.python310;

        # Make a Python package with the Image Generating Plugin source code and third-party dependencies 
        # defined in the pyproject.toml file using the mkPoetryApplication function
        myApp = mkPoetryApplication { 
            python = myPython;
            projectDir = ./.; 
            preferWheels = true;
          };

      in
      rec {
        packages = {
          app_package = myApp;
          # set the app package to the default package
          default = packages.app_package;
        };

        devShells.default = shell {
          packages = [ poetry2nix.packages.${system}.poetry packages.myapp ];
        };
      });
}