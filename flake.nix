# This flake builds both the Camera Traps engine (Rust) binary as well as the
# Camera Traps "executor" shell script. The former is based on Crane and for the latter
# we use mkShellApplication. 

{
  description = "A Nix Flake for the ICICLE Camera Traps Application";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    # rust-overlay = {
    #   url = "github:oxalica/rust-overlay";
    #   inputs = {
    #     nixpkgs.follows = "nixpkgs";
    #     flake-utils.follows = "flake-utils";
    #   };
    crane.url = "github:ipetkov/crane";
    
    # TODO -- eventually we will depend on the other flakes
    # image_generating_plugin.url = "github:tapis/camera-traps/external_plugins/image_generating_plugin";
    # image_scoring_plugin.url = "github:tapis/camera-traps/external_plugins/image_scoring_plugin";    
  };

 outputs = 
 {
    self,
    nixpkgs,
    flake-utils,
    # rust-overlay,
    crane,
    # image_generating_plugin,
    # image_scoring_plugin
 }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # Standard nix packages
        pkgs = nixpkgs.legacyPackages.${system};
        
        # Crane is used for building the Rust Camers Traps Engine        
        craneLib = crane.lib.${system};
        
        camera_traps_engine =
              craneLib.buildPackage {
                src = craneLib.cleanCargoSource ./.;
                buildInputs = with pkgs; [
                  # the engine requires libzmq 
                  zeromq
                ];
                nativeBuildInputs = with pkgs; [
                  pkg-config
                ];
              };
      in
      rec {

         packages.default = camera_traps_engine;
      });

}