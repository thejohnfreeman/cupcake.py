# :cupcake: cupcake.py

Make C++ a piece of cake.

[![GitHub checks](https://img.shields.io/github/check-runs/thejohnfreeman/cupcake.py/master?label=tests)](https://github.com/thejohnfreeman/cupcake.py/actions?query=branch%3Amaster)
[![version](https://img.shields.io/pypi/v/cupcake)](https://pypi.org/project/cupcake/)
![Python version](https://img.shields.io/pypi/pyversions/cupcake?color=orange)


Cupcake is an all-in-one build tool and package manager for C++,
like [Cargo][] for Rust, [npm][] for JavaScript, or [Poetry][] for Python.
It serves the complete package lifecycle, all from the command line,
with no manual editing of configuration files required:

- Create a new project.
- Search, add, or remove package dependencies.
- Build, test, or install your project.
- Run or debug executables in your project.
- Publish your package.

Cupcake is implemented as a thin layer on top of [CMake][] and [Conan][].
It assembles and runs the commands that you would otherwise write yourself.
It offers a smaller interface that is easier to understand and use,
but it aims to support the most common project patterns.
Cupcake does not support all of the same options as CMake and Conan,
but the options that it does support are remembered
in a local configuration file so that you don't have to repeat them.

Cupcake is designed to be easy to try, with no lock-in.
If you create a project with Cupcake and later decide to stop using it,
you are still left with a functional CMake and Conan project.
If you find that you need an option that is missing from Cupcake,
then you can always invoke Conan or CMake directly.


## Interface

There are two dimensions on which to divide Cupcake commands.
The first is _general_ vs _special_ commands.
**General commands** work with any CMake project,
whether or not it has a Conan recipe.
**Special commands** work only with conforming projects.
Many special commands require a **Cupcake metadata file**, `cupcake.json`,
to easily share metadata between the Conan recipe and the CMake configuration.
The easiest way to make a project conform is to create it with
[`cupcake new --special`](#cupcake-new).

The second dimension is _source_ vs _build_ commands.
**Source commands** interact with only the project's **source directory**.
You can choose the source directory for any such command
with option `--source-dir` (`-S`).
**Build commands** interact with the project's **build directory** too.
You can choose the build directory for any such command
with option `--build-dir` (`-B`).
The Cupcake build directory is not the same thing
as the CMake binary directory.
The Cupcake build directory may house _multiple_ CMake binary directories,
as well as a Conan output folder and anything else Cupcake wants to store.
It is not meant for public consumption except through Cupcake build commands:

- [`conan`](#cupcake-conan) and [`cmake`](#cupcake-cmake) configure the build
    directory. You will typically never need to run these commands directly.
- [`clean`](#cupcake-clean) removes the build directory.
- [`build`](#cupcake-build), [`test`](#cupcake-test), and
    [`install`](#cupcake-install) effectively run
    `cmake --build`, `ctest`, and `cmake --install`, respectively.
- [`exe`](#cupcake-exe) and [`debug`](#cupcake-debug) are special commands
    that run `cmake --build` for specific custom targets defined for
    executables by [cupcake.cmake].

A Cupcake command may depend on other Cupcake commands.[^1]
For example, `build` depends on `cmake`, which depends on `conan`.
`test` depends on `cmake` too, but not on `build`.

[^1]: In theory, any Cupcake command may have dependencies,
but in practice, only build commands do.

<!-- TODO: dot graph with command DAG -->

Each Cupcake command automatically runs the commands it depends on.
You can run just the final command you are interested in.
You do not have to walk through manually configuring your build directory
like you would with Conan and CMake.
You can skip straight to `cupcake test` in a fresh clone, for instance.

Cupcake commands inherit all of the options of their
direct _and indirect_ dependencies.
You can pass Conan options to `cupcake conan`,
or you can pass them to `cupcake build`, `cupcake test`, and so on.
Options that affect the state of the build directory
are stored in a [**Cupcake configuration file**](#cupcaketoml).
The default is `.cupcake.toml` in the project source directory,
but you can override it with the option `--config`.
You can manually edit the configuration file if you want.
(Cupcake preserves any comments in it.)
Options that do _not_ affect the state of the build directory
are typically not stored.
Exceptions, e.g. `--jobs`, are noted where they appear.

Whether or not you use a [multi-config][1] CMake generator,
Cupcake models a multi-config build directory.
Because the word "configuration" is used in so many contexts
with different meanings (sometimes it is called "build type"),
Cupcake calls CMake configurations **flavors**.
Flavors in Cupcake are case-insensitive, but lowercase is preferred.
Many commands, e.g. `build` and `test`, work on one flavor at a time,
the **selected** flavor.
You can override the selected flavor on the command line,
with option `--flavor`, and that selection will be saved for the next command.

When you pass options that affect the state of the build directory,
e.g. by selecting a different flavor,
Cupcake will automatically reconfigure the build directory
with those new options,
but only the parts that need to be reconfigured,
to preserve work from previous builds.
The same happens if you change configuration files,
e.g. `CMakeLists.txt` or the Conan recipe,
that affect the state of the build directory,
e.g. when you change branches in a Git repository.
You should never need to manually configure or reconfigure the build directory.
Let Cupcake figure out for you what is required.
But if Cupcake ever does make a mistake,
all of this is designed to let you blow away the build directory
and recreate it with exactly the same options just by running `cupcake build`.


<a id="toc"></a>

### General commands

- [`build`](#cupcake-build) Build the selected flavor.
- [`cache`](#cupcake-cache) Copy a package to your local cache.
- [`clean`](#cupcake-clean) Remove the build directory.
- [`cmake`](#cupcake-cmake) Configure CMake for at least the selected flavor.
- [`conan`](#cupcake-conan) Configure Conan for all enabled flavors.
- [`install`](#cupcake-install) Install the selected flavor.
- [`publish`](#cupcake-publish) Upload a package.
- [`search`](#cupcake-search) Search for packages.
- [`select`](#cupcake-select) Select a flavor.
- [`test`](#cupcake-test) Execute tests.


### Special commands

- [`add`](#cupcake-add) Add one or more requirements.
- [`add:exe`](#cupcake-addexe) Add one or more executables.
- [`add:header`](#cupcake-addheader) Add one or more public headers to an existing library.
- [`add:lib`](#cupcake-addlib) Add one or more libraries.
- [`add:test`](#cupcake-addtest) Add one or more tests.
- [`debug`](#cupcake-debug) Debug an executable.
- [`exe`](#cupcake-exe) Execute an executable.
- [`link`](#cupcake-link) Link a target to one or more libraries.
- [`list`](#cupcake-list) List targets and their links.
- [`new`](#cupcake-new) Create a new project.
- [`remove`](#cupcake-remove) Remove a requirement.
- [`remove:exe`](#cupcake-removeexe) Remove one or more executables.
- [`remove:lib`](#cupcake-removelib) Remove one or more libraries.
- [`remove:test`](#cupcake-removetest) Remove one or more tests.
- [`unlink`](#cupcake-unlink) Unlink a target from one or more libraries.
- [`version`](#cupcake-version) Print or change the package version.


### `.cupcake.toml`

This section describes the common settings, used by multiple commands,
that are persisted in the Cupcake configuration file.
Other settings that are persisted in the configuration file
but used by only a single command are documented under that command.
The only two settings that _cannot_ be persisted in the configuration file
are the source directory and the configuration file path,
but they are documented here anyways.

The way settings work in Cupcake is unique, I think, but easy to explain.
If you do not override a setting with a command-line option,
then its default is taken from the configuration file.
If it is missing in the configuration file too,
then the default is hard-coded in Cupcake
(and visible in the help string for the option).
This way, if you're in the habit of repeating long command lines
full of options for Conan and CMake,
then you can do the same with Cupcake and expect the same behavior.
But with Cupcake,
once you've assigned a setting through a command-line option,
then you can just repeat the command with no options
and trust it will "do the same thing as last time".
You can build a command incrementally
and repeat it without searching through history.

As a [TOML][] file, the configuration file represents an object.
In the table below, the Key column defines the path in that object
to the property for the setting.
The Options column lists all the command-line options that affect the setting.
Not all settings can be controlled by a command-line option.
They must be manually edited in the configuration file instead.[^2]

[^2]: In the future, I plan to add more command-line options for settings,
and to enable overrides from environment variables.


| Setting | Key | Options | Type | Default
|---|---|---|---|---
| **source directory** | | `--source-dir`, `-S` | path | `.`
| **configuration file** | | `--config` | path | `.cupcake.toml`
| **build directory** | `.directory` | `--build-dir`, `-B` | path | `".build"`
| **verbosity level** | `.verbosity` | `--verbose`, `-v`, `--quiet`, `-q` | integer in range [0, 3] | `0`
| **selected flavor** | `.selection` | `--flavor` | string | `"release"`
| **enabled flavors** | `.flavors` | | list of strings | `["release"]`
| **parallelism limit** | `.jobs` | `--jobs`, `-j`, `--parallel` | positive integer | number of logical processors
| **Conan executable** | `.path.conan` | | path | `conan`
| **CMake executable** | `.path.cmake` | | path | `cmake`
| **CTest executable** | `.path.ctest` | | path | `ctest`

If the configuration file or build directory are relative paths,
then they are evaluated relative to the source directory.
If the executables are relative paths,
then they are evaluated like any other command,
i.e. relative to the `PATH` environment variable.

Verbosity is incremented by `--verbose`/`-v`
and decremented by `--quiet`/`-q`, and clamped to the range [0, 3].

Even though the level of parallelism does not affect
the state of the build directory, it is persisted for a reason.
Cupcake builds in parallel by default, unlike CMake.
The default parallelism limit
matches the number of logical processors detected by Cupcake.
If your translation units are small, and your build is CPU-constrained,
then this is typically the right choice.
But if your translation units are large,
and your build is memory-constrained instead,
then this choice can lead to memory pressure and even crashing builds.
The right choice for the limit depends on the machine _and_ the project,
and thus it is persisted in a setting.


### `cupcake build`
[:arrow_up:](#toc) :hash: [general](#interface), [build](#interface)

### `cupcake cache`
[:arrow_up:](#toc) :hash: [general](#interface), [source](#interface)

### `cupcake clean`
[:arrow_up:](#toc) :hash: [general](#interface), [build](#interface)

### `cupcake cmake`
[:arrow_up:](#toc) :hash: [general](#interface), [build](#interface)

### `cupcake conan`
[:arrow_up:](#toc) :hash: [general](#interface), [build](#interface)

### `cupcake install`
[:arrow_up:](#toc) :hash: [general](#interface), [build](#interface)

### `cupcake publish`
[:arrow_up:](#toc) :hash: [general](#interface), [source](#interface)

### `cupcake search`
[:arrow_up:](#toc) :hash: [general](#interface), [source](#interface)

### `cupcake select`
[:arrow_up:](#toc) :hash: [general](#interface), [source](#interface)

### `cupcake test`
[:arrow_up:](#toc) :hash: [general](#interface), [build](#interface)


### `cupcake add`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake add:exe`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake add:header`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake add:lib`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake add:test`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake debug`
[:arrow_up:](#toc) :hash: [special](#interface), [build](#interface)

### `cupcake exe`
[:arrow_up:](#toc) :hash: [special](#interface), [build](#interface)

### `cupcake link`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake list`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake new`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake remove`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake remove:exe`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake remove:lib`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake remove:test`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake unlink`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)

### `cupcake version`
[:arrow_up:](#toc) :hash: [special](#interface), [source](#interface)


[Cargo]: https://doc.rust-lang.org/stable/cargo/
[npm]: https://docs.npmjs.com/about-npm
[Poetry]: https://python-poetry.org/
[CMake]: https://cmake.org/cmake/help/latest/
[Conan]: https://github.com/conan-io/conan
[cupcake.cmake]: https://github.com/thejohnfreeman/cupcake.cmake
[TOML]: https://toml.io/

[1]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#build-configurations
