# cupcake.py

- like Cargo, NPM, Poetry, Stack for C++
- all-in-one build tool and package manager
- serves the complete package lifecycle:
    - creation
    - link to other packages
    - build, test, install
    - pack and publish, ready to be linked by another package


cupcake.py is implemented as a thin layer on top of CMake and Conan.
it assembles and executes the commands that you would be.
it is offering a smaller interface that is easier to understand and use.
I believe it supports the most common use cases,
and will be good enough for more than 90% of C++ programmers.
it does not support all the same options as CMake and Conan,
but the options it does support are remembered in a local configuration file
so that you don't have to repeat them all the time.

- Cupcake is designed to be easy to try, with no lock-in.
- if you create a project with Cupcake and later decide to stop using it, you
    are still left with a normal CMake and Conan project.
- if you find that you need an option that is missing from Cupcake, then you can
    always invoke Conan and CMake directly.

- two sets of commands:
- general and special
- general commands work with any CMake codebase, whether or not it uses Conan.
- special commands work only with conforming projects.
- the easiest way to make a project conform is to create it with Cupcake.
- Cupcake's default project template depends on cupcake.cmake, which
    implements the CMake side of things.

- build directory general commands are:
- clean, conan, cmake, build, test, install
- special commands are:
- exe, debug.
- conan and cmake commands configure the build directory.
- clean removes it.
- build, test, and install effectively run `cmake --build`, `ctest`, and
    `cmake --install`.
- exe and debug run `cmake --build` for specific custom targets.

- some commands depend on others.
- they will automatically run their ancestors. you can just run the terminal command
    you are interested in. you do not have to walk through
    manually configuring your build directory. you can skip straight to
    `cupcake test`, for instance.
- commands inherit all of the options of their ancestors.
- options that affect the state of the build directory are stored in a local
    configuration file, option `--config`, default `.cupcake.toml`.
- you can manually edit the configuration file if you want. Cupcake preserves
    any comments in it.
- options that do not affect the state of the build directory are typically
    not stored. exceptions, e.g. `--jobs`, are documented.

- when you pass options that affect the state of the build directory,
    Cupcake will automatically reconfigure the build directory with those new
    options.
- same for if you change configuration files, e.g. CMakeLists.txt or the Conan
    recipe, that affect the state of the build directory.
- you do not need to manually run the configuration steps.
- I personally never run the conan or cmake commands directly.

- whether or not you use a multi-config CMake generator, Cupcake models
    a multi-config build directory.
- because "config" is used in so many contexts with different meanings,
    Cupcake calls CMake configs **flavors**.
- many commands work on one flavor at a time, e.g. `build` and `test`.
- these commands will work on the **selected** flavor.
- you can override the selection on the command line, and that selection will
    be saved for the next command.
- you don't need to manually reconfigure the build directory when changing
    flavors. let Cupcake figure out for you whether it is required.
- you can see the current selection with `cupcake select`.

general:
  build        Build the selected flavor.
  cache        Copy a package to your local cache.
  clean        Remove the build directory.
  cmake        Configure CMake for at least the selected flavor.
  conan        Configure Conan for all enabled flavors.
  install      Install the selected flavor.
  publish      Upload a package.
  search       Search for packages.
  select       Select a flavor.
  test         Execute tests.

special:
  add          Add one or more requirements.
  add:exe      Add one or more executables.
  add:header   Add one or more public headers to an existing library.
  add:lib      Add one or more libraries.
  add:test     Add one or more tests.
  debug        Debug an executable.
  exe          Execute an executable.
  link         Link a target to one or more libraries.
  list         List targets and their links.
  new          Create a new project.
  remove       Remove a requirement.
  remove:exe   Remove one or more executables.
  remove:lib   Remove one or more libraries.
  remove:test  Remove one or more tests.
  unlink       Unlink a target from one or more libraries.
  version      Print or change the package version.
