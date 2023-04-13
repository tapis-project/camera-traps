# This flake builds both the Camera Traps engine (Rust) binary as well as the
# Camera Traps "executor" shell script. The former is based on Crane and for the latter
# we use writeShellScript. 

{
  description = "A Nix Flake for the ICICLE Camera Traps Application";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    crane.url = "github:ipetkov/crane";
    
    # Point to the plugin flakes as inputs; not the use of the dev branch and the subdirectory (with the `dir` attr).
    # In the future, we may want to point to main once we have the flakes moved up.
    image_generating_plugin.url = "github:tapis-project/camera-traps/dev?dir=external_plugins/image_generating_plugin";
    image_scoring_plugin.url = "github:tapis-project/camera-traps/dev?dir=external_plugins/image_scoring_plugin";    
  };

 outputs = 
 {
    self,
    nixpkgs,
    flake-utils,
    crane,
    image_generating_plugin,
    image_scoring_plugin
 }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # Standard nix packages
        pkgs = nixpkgs.legacyPackages.${system};
        
        # Crane is used for building the Rust Camers Traps Engine        
        craneLib = crane.lib.${system};
        
        # Build the Rust engine
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

        # Point at the packages for this system
        image_generating_plugin_pkg = image_generating_plugin.packages.${system}.default;
        image_scoring_plugin_pkg = image_scoring_plugin.packages.${system}.default;
        
        # Build the shell application which starts all three components
        camera_traps_executor = pkgs.writeShellApplication {
            name = "camera-traps-executor";
            text = ''
              ${camera_traps_engine}/bin/camera-traps & ${image_generating_plugin_pkg}/bin/image_generating_plugin & ${image_scoring_plugin_pkg}/bin/image_scoring_plugin
            '';
        };

      in
      rec {
         packages = {
            engine_package = camera_traps_engine;
            executor_package = camera_traps_executor;
            default = packages.executor_package;
         };
         
      });

}