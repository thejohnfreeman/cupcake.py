# Cupcake Tutorial

This is a course walking through how to start, develop, and share
a C++ project using [Cupcake][].

We'll start by creating a new project
that depends on [fmt][]
and exports a library and an executable
for translating sentences to [Pig Latin][].
Then we'll package that project with [Conan][],
upload it to [Redirectory][],
and create a second project that depends on it.
All of these steps are demonstrated in a separate GitHub project,
[try-cupcake][], that is linked throughout.
Each [commit][13] in the `master` branch of that project
pertains to a step in this tutorial.
I encourage you to walk through those commits
and try out the example commands in each commit message.


## Installation

Cupcake is designed to work with [CMake][] projects,
with and without the [Conan][] C++ package manager.
The Cupcake project template that we'll be using in this tutorial
assumes that you have both installed, as well as a C++ compiler.
Cupcake works with both major versions 1.x and 2.x of Conan,
and its project template requires CMake >= 3.21.

Additionally, Cupcake assumes that Conan is already configured.
If you've never used Conan before,
then this should be all the configuration you need to get started:

```sh
# conan 1.x
> conan profile new --detect
# conan 2.x
> conan profile detect
```

Cupcake is distributed as a Python package.
It depends on another Python package that, unfortunately,
[conflicts][14] on its package name with a dependency of Conan 1.x.
Thus, I recommend that you install Conan with [pipx][],
to isolate its installation from other Python packages,
even if you are using Conan 2.x:

```sh
> pipx install cupcake
```


## `new`

You can scaffold a new C++ project with Cupcake's `new` command.
It takes a single optional argument that is
the path to the project's root directory.
The directory need not already exist,
and the default is the current directory.
If the directory exists, it should be empty,
but you can scaffold into a non-empty directory with `--force`.

Each project must have a name.
The name can have only lowercase letters, numbers, and hyphens (-),
and it must start with a letter.[^1]
The default name is the name of the project's root directory,
but you can choose a different name with the `--name` option.

Our first example project is going to translate Pig Latin,
so let's call it `pig-latin`:

```
cupcake new pig-latin
```

Each new Cupcake project comes by default with:

- one (binary) [library][5] named after the project
    with one [public header][6]
- one [executable][7] named after the project
- one [test][8] named after the project
- a root [`CMakeLists.txt`][9]
- a [Conan recipe][10]
- a [`.gitignore`][11] that ignores Cupcake's default configuration file,
    build directory, and install directory
- a dependency on the [`cupcake.cmake`][] CMake module
- a test dependency on [`doctest`][]

We will use all of these parts in this tutorial,
but in your own projects,
one of your first acts might be to remove the parts that you don't need.
Alternatively, you can exclude their creation with options to `cupcake new`,
e.g. `--no-executable` or `--no-tests`.
You can examine the options for any Cupcake command with `--help`.

There is an important distinction to note here:
`cupcake new` generates a _Cupcake_ C++ project,
which is a C++ project following a prescribed structure.
Cupcake works with _any_ CMake project,
whether or not it is a Cupcake project,
and even whether or not it has a Conan recipe,
but it has some special commands that work _only_ with Cupcake projects,
e.g. adding and removing dependencies.
Consult the [README][] to learn more about the differences between
Cupcake's general and special commands.


## The `cupcake.cmake` CMake module

Cupcake's project template leverages a CMake module named [`cupcake.cmake`][]
to encapsulate CMake boilerplate and best practices and let us write
minimal CMake.
The template's Conan recipe (`conanfile.py`)
includes a dependency on a Conan package named
`cupcake.cmake` that exports the CMake module.
That package is available through [Redirectory][],
a free public Conan package server,
which you can add as a remote:

```
conan remote add redirectory https://conan.jfreeman.dev
```

Alternatively, you can add the package to your local Conan cache
with `cupcake cache`, which works for GitHub URLs:

```
cupcake cache https://github.com/thejohnfreeman/cupcake.cmake
```


## Commands

A new Cupcake project can be built out-of-the-box with `cupcake build`.
Building is a 3-step process:

- Use Conan to build dependencies and generate CMake files.
- Use CMake to generate build system files.
- Use the underlying build system to compile and link your source files.

Each of these steps has a separate Cupcake command
(`conan` then `cmake` then `build`),
but you don't need to manually execute them all.
Each step depends on the one before it, and will always execute it.

Commands may short-circuit however.
Each command has inputs,
including command-line options and files in the project.
For example, the `conan` command depends on the contents of the Conan recipe,
whether it is `conanfile.py`
(as it is in the Cupcake project template)
or `conanfile.txt`.
If a command detects no change in its inputs from the last time it
successfully completed, then it will do nothing.

There are more commands with dependencies:
`test` depends on `cmake`,
`install` depends on `build`,
and they all depend on `select` (more on that later).

Commands inherit the command-line options of their prequisites, transitively,
and pass them along.
That means in a single `build` command,
you can pass options for both the `conan` and `cmake` commands.
In general, you don't need to remember which commands to run or in what order.
Just run the command for your ultimate goal, e.g. `install` or `test`,
and let Cupcake figure out how to get there.

Cupcake commands that defer to lower-level tools like Conan and CMake
will print the subcommands that they run.
Hypothetically, you could have run those subcommands yourself,
except that Cupcake performs additional bookkeeping
to track the state of your build directory.
Subcommands are shown just to let you know
what Cupcake is doing under the hood.
Cupcake isn't doing anything that you couldn't have done for yourself.
It is just freeing you from the mental burden of
remembering the state of your build directory,
and the physical burden of writing out long commands with many options.


## Configuration

Cupcake has a unique approach to configuration.
Command options typically have default values.
Take `--build-dir`, for example.
It is an option for the commands `conan` and `clean`
(and every command that depends on them, directly or indirectly).

When you override `--build-dir` on the command line,
the value is saved in your configuration file.
The value in your configuration file becomes the new default when you don't
pass `--build-dir` on the command line.
Most options work like this.
Their defaults are not constants.
Instead, they are taken from the configuration file.

There are a couple of notable exceptions that are not (and cannot)
be saved in the configuration file.
The path to the source directory is one.
It's default is `.`, but it can be overridden with `--source-dir`.
The path to the configuration file itself is the other.
The default for it is always `.cupcake.toml`,
but it can be overridden with the `--config` option,
and any relative path is interpreted relative to the source directory.

By using the configuration file to fill in defaults,
Cupcake lets you blow away your build directory (with `cupcake clean`)
and re-create it (with `cupcake build`)
without having to recite the exact same command-line options
for Conan or CMake.

The configuration file is considered part of a local build.
Generally, it should not be included in version control.
The default configuration file path (`.cupcake.toml`)
is included in the `.gitignore` of the Cupcake project template.


## `install`

A Cupcake project exports all of its non-private libraries and executables.
The **exports** are what the project installs
and what downstream projects can import.

Installing the project with `cupcake install` will install its exports
at well-known locations, according to the standards of [`GNUInstallDirs`][],
under a given prefix:

- `bin` for [runtime][] exports
- `lib` for [library][] and [archive][] exports
- `include` for public headers
- `share` for CMake [Package Configuration Files][PCF]

The default prefix is `.install` (relative to the source directory),
but it can be overridden with `--prefix` to,
e.g., `/usr/local` or `C:\Program Files`.
The idea behind this default is to let you test an install locally
and inspect the results before invoking elevated privileges.

I recommend installing whenever you want to manually test an export,
e.g. to run an executable.
Building alone will create the exports
but force you to fish around in the build directory to find them,
and the build directory should be considered private property of the build tool.
Testing the installation will guarantee a good experience for your users, too,
who will generally never look in a build directory,
and just skip straight to installation.


## Symbols

Add a new function in our library's public header,
implement it in the library source, and use it in the executable.
Then try to build the project using shared libaries
with `cupcake build --shared`.
You will get a linker error if you forgot to export the function.

Shared libraries compiled with GCC or Clang will
implicitly export all symbols by default,
while shared libraries compiled with Visual Studio will not.
In [C++ modules][15], all exports must be explicitly declared.
That is a language rule; the decision is no longer left to the compiler.
To follow best practices and prepare developers for the transition to modules,
the Cupcake project template requires explicit exports for symbols,
regardless of compiler.

To export a symbol, you must mark it with an annotation.
`cupcake.cmake` [generates][1] a header on the include path, `{library}/export.hpp`,
that you can include to get a macro, `{LIBRARY}_EXPORT`,
that expands to the text of the annotation.
The annotation is only necessary in the header file,
assuming you include that header in the same file
where you implement the symbol.


## Flavors

Up to now, we've been building and installing a single *flavor*.
A **flavor** is what CMake calls a "build type" or "[configuration][3]",
but those terms can be ambiguous in many contexts,
so Cupcake calls them "flavors".
Flavors have implications on the default compiler flags
and default [MSVC runtime library][2].

Some CMake [generators][4] support multiple flavors in the same build
directory, a.k.a. "multi-configuration generators" like Visual Studio or
Xcode,
while others support only one at a time, a.k.a. "single configuration
generators" like Unix Makefiles.
Cupcake always supports multiple flavors in its build directory,
and it achieves this for single configuration CMake generators by maintaining
multiple CMake build directories within the Cupcake build directory.

All flavor-conscious Cupcake commands work on a single flavor at a time.
That flavor is called the **selection**.
The default selection is `release`,
but it can be overridden with the `--flavor` option,
and any explicit override will be saved in the configuration file.


## `test`

Tests for the project are in the `tests` subdirectory.
A **test** is what [CTest][] calls a test:
an executable that returns 0 if and only if it passed.

The `tests` subdirectory is included in the CMake project
only when tests are enabled,
i.e. when the CMake option `BUILD_TESTING` is on,
which it is by default.

You can build and execute tests with `cupcake test`.
`cupcake.cmake` will rebuild tests if their sources have changed.


## Imports

You can add an import with `cupcake add`.
It takes a query argument that it uses
to search your local and remote Conan caches.
You can first test what your query will return with `cupcake search`:

```
cupcake search boost
```

The results are listed in what Cupcake thinks is the version order.
The highest version is printed last
so that it is always visible in your terminal
no matter how many results are found.
The last result will be the one chosen by `cupcake add`.
You can always search for a specific version so that it is the only result:

```
cupcake search boost/1.86.0
```

Let's add [fmt][] as an import.
It is available in [Conan Center][] under the package name [`fmt`][16]:

```
cupcake add fmt
```

This adds the package as an **import**[^2] in `cupcake.json`.
`cupcake.json` is the Cupcake project metadata file
that Cupcake special commands use.
Each import belongs to one or more **groups**.
An import with no explicit groups belongs implicitly to the `main` group.
The Cupcake project template comes with one `test` group import, [`doctest`][].
You can specify groups when adding an import with option `--group`.

The Cupcake project template links the library against all `main` imports.
You can always remove that link, but it means that out-of-the-box you can add
an import with `cupcake add` and immediately start writing C++ code to
`#include` its headers without ever touching the Conan recipe or CMake files.

Once you've changed `cupcake.json`,
`cupcake build` will reconfigure the build system and rebuild the project.


## Packaging

Cupcake can publish a package to your local Conan cache with `cupcake cache`.
That is all you need to use it in another project on your own machine.
If you want to share a package publicly,
then you can publish it to a remote Conan package server with `cupcake publish`.

The Conan recipe (`conanfile.py`) in the Cupcake project template
builds a package by installing it into a temporary directory.
The CMake configuration calls the function
[`cupcake_install_cpp_info`][17] from `cupcake.cmake`
to generate and install Conan package metadata (in a file, `cpp_info.py`)
to be ingested by the recipe.

After caching `pig-latin`, loop back around to the start of this tutorial
and try using it in a new project:

- Create a second project with `cupcake new`.
- Add `pig-latin` as an import with `cupcake add`.
- Edit the library to `#include <pig-latin/pig-latin.hpp>` and call its API.
- Edit the executable to use the library.
- Edit the test to test the library.
- Test and install.


[^1]: See [`cupcake.cmake`][] for an explanation of the constraints on
    a Cupcake C++ Project and the reasons for them.
[^2]: What Cupcake calls "imports", Conan calls "requirements".

[try-cupcake]: https://github.com/thejohnfreeman/try-cupcake
[project-template-cpp]: https://github.com/thejohnfreeman/project-template-cpp
[rippled]: https://github.com/XRPLF/rippled.git
[Cupcake]: https://github.com/thejohnfreeman/cupcake.py
[`cupcake.cmake`]: https://github.com/thejohnfreeman/cupcake.cmake
[`doctest`]: https://github.com/doctest/doctest
[Conan]: https://conan.io/
[fmt]: https://github.com/fmtlib/fmt
[Pig Latin]: https://en.wikipedia.org/wiki/Pig_Latin
[Conan]: https://docs.conan.io/2/
[libxrpl]: https://github.com/XRPLF/rippled/blob/develop/conanfile.py#L146-L154
[`ripple::Seed`]: https://xrplf.github.io/rippled/classripple_1_1Seed.html
[`GNUInstallDirs`]: https://cmake.org/cmake/help/latest/module/GNUInstallDirs.html
[runtime]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#runtime-output-artifacts
[library]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#library-output-artifacts
[archive]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#archive-output-artifacts
[PCF]: https://cmake.org/cmake/help/latest/manual/cmake-packages.7.html#package-layout
[Redirectory]: https://github.com/thejohnfreeman/redirectory
[CMake]: https://cmake.org/cmake/help/latest/index.html
[pipx]: https://github.com/pypa/pipx
[README]: https://github.com/thejohnfreeman/cupcake.py/tree/readme?tab=readme-ov-file#interface
[CTest]: https://cmake.org/cmake/help/book/mastering-cmake/chapter/Testing%20With%20CMake%20and%20CTest.html
[Conan Center]: https://conan.io/center

[1]: https://cmake.org/cmake/help/latest/module/GenerateExportHeader.html
[2]: https://cmake.org/cmake/help/latest/prop_tgt/MSVC_RUNTIME_LIBRARY.html
[3]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#build-configurations
[4]: https://cmake.org/cmake/help/latest/manual/cmake-generators.7.html
[5]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/pig-latin/src/libpig-latin.cpp
[6]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/pig-latin/include/pig-latin/pig-latin.hpp
[7]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/pig-latin/src/pig-latin.cpp
[8]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/pig-latin/tests/pig-latin.cpp
[9]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/pig-latin/CMakeLists.txt
[10]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/pig-latin/conanfile.py
[11]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/pig-latin/.gitignore
[12]: https://github.com/thejohnfreeman/cupcake.cmake/tree/master/structure.md
[13]: https://github.com/thejohnfreeman/try-cupcake/commits/master/
[14]: https://github.com/conan-io/conan/pull/16383
[15]: https://en.cppreference.com/w/cpp/language/modules
[16]: https://conan.io/center/recipes/fmt
[17]: https://github.com/thejohnfreeman/cupcake.cmake?tab=readme-ov-file#cupcake_install_cpp_info
