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
        pkgs = nixpkgs.legacyPackages.${system};
        shell = shell-utils.myShell.${system};
      in
      rec {
        packages = {
          myapp = mkPoetryApplication { projectDir = ./.; };
          myenv = mkPoetryEnv { projectDir = ./.; };
          default = self.packages.${system}.myapp;
        };

        devShells.default = shell {
          packages = [ poetry2nix.packages.${system}.poetry packages.myapp ];
        };
      });
}