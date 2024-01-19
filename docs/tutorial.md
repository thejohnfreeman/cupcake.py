# Cupcake Tutorial

This is a course walking through how to start, develop, and share
a C++ project using [Cupcake].

We'll start by creating a new project, named `seedgen`,
that depends on [libxrpl]
and exports a library and an executable
for generating random [`ripple::Seed`]s.
Then we'll package that project with Conan
and create a second project that depends on it.
All of these steps are demonstrated in a separate GitHub project,
[try-cupcake], that is linked throughout.


## `new`

You can scaffold a new C++ project with Cupcake's `new` command.
It takes a single optional argument that is
the path to the project's root directory.
The directory need not exist, and the default is the current directory.
If the directory does exist, it should be empty,
but you can scaffold into a non-empty directory with `--force`.

Each project must have a name.
The name can have only lowercase letters and numbers
and must start with a letter.[^1]
The default name is the name of the root directory,
but you can choose a different name with the `--name` option.

Our example project is going to generate seeds, so let's call it `seedgen`:

```
cupcake new seedgen
```

Each new Cupcake project comes by default with:

- one (binary) [library][5] named after the project
    with one [public header][6]
- one [executable][7] named after the project
- one [test][8] named after the project
- a root [`CMakeLists.txt`][9]
- a [Conan recipe][10]
- a [`.gitignore`][11] that ignores Cupcake's default configuration file and
    build and install directories
- a dependency on the [`cupcake`] CMake module
- a test dependency on [`doctest`]

We will use all of these parts in this tutorial,
but in your own projects,
one of your first acts might be to remove the parts that you don't need.


## The `cupcake` CMake module

Cupcake's default template leverages a CMake module named `cupcake`
to encapsulate CMake boilerplate and best practices and let us write
minimal CMake.
The template's Conan recipe includes a dependency on a Conan package named
`cupcake` that exports the CMake module.
That package is available through [Redirectory]
which you can add as a remote[^3]:

```
conan remote add redirectory https://conan.jfreeman.dev
```

Alternatively, you can add it to your local cache with `cupcake pack`,
which works for GitHub URLs:

```
cupcake pack https://github.com/thejohnfreeman/project-template-cpp/tree/master/cupcake
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
(as it is in the default Cupcake project template)
or `conanfile.txt`.
If a command detects no change in its inputs from the last time it
successfully completed, then it will do nothing.

There are more commands with dependencies:
`test` depends on `cmake`,
`install` depends on `build`,
and they all depend on `select` (more on flavors in a future lesson).

Commands inherit the command-line options of their prequisites, transitively,
and pass them along.
That means in a single `build` command,
you can pass options for both the `conan` and `cmake` commands.
In general, you don't need to remember which commands to run or in what order.
Just run the command for your ultimate goal, e.g. `install` or `test`,
and let Cupcake figure out how to get there.

Cupcake commands that defer to lower-level tools like Conan and CMake will
print the subcommands that they run.
Hypothetically, you could have run those subcommands yourself,
except that Cupcake does additional bookkeeping to track input states.
Subcommands are shown just to let you know what Cupcake is doing under the
hood.
Cupcake isn't doing anything that you couldn't have done for yourself.
It is just freeing you from the mental burden of remembering the state of your
build directory.


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

There are a couple of notable exceptions that are not (cannot)
be saved in the configuration file.
The path to the configuration file itself is one.
The default for it is always `.cupcake.toml`,
but it can be overridden with the `--config` option.
The path to the source directory is the other.
It's default is `.`, but it can be overridden with `--source-dir`.

By using the configuration file to fill in defaults,
Cupcake lets you blow away your build directory (with `cupcake clean`)
and re-create it (with `cupcake build`)
without having to recite the exact same command-line options
for Conan or CMake.

The configuration file is part of a local build.
Generally, it should not be included in version control.
The default configuration file path is included in the `.gitignore`
of the default Cupcake project template.


## `install`

At the package level,
a Cupcake project **exports** all of its non-test artifacts,
i.e. the libraries and executables defined in the root `CMakeLists.txt`
using `cupcake_add_library` and `cupcake_add_executable`.
The exports are what the project installs
and what downstream projects can import.

Installing the project with `cupcake install` will install its exports
in well-known locations, according to the standards of [`GNUInstallDirs`],
under a given prefix:

- `bin` for [runtime] outputs
- `lib` for [library] and [archive] outputs
- `include` for public headers
- `share` for CMake [Package Configuration Files][PCF]

The default prefix is `.install`, but it can be overridden with `--prefix`
to, e.g., `/usr/local` or `C:\Program Files`.
The idea behind this default is to let you test an install locally
and inspect the results before invoking elevated privileges.

We recommend installing whenever you want to manually test an output,
e.g. to run an executable.
Building will make outputs available
but force you to fish around in the build directory,
which should be considered property of the build tool.
Testing after installing will guarantee a good experience for your users, too,
who will generally never look in a build directory,
and just skip straight to installation.


## Symbols

Add a new function in our library's public header,
implement it in the library source, and use it in the executable.
Then try to build the project using shared libaries
with `cupcake build --shared`.
You will get a linker error if you forgot to *export* the function.

Shared libraries compiled with GCC or Clang will
implicitly export all symbols by default,
while shared libraries compiled with Visual Studio will not.
In C++ modules, all exports must be explicitly declared.
That is a language rule; the decision is no longer left to the compiler.
To follow best practices and prepare developers for the transition to modules,
the default Cupcake project template does not implicitly export any symbols
with any compiler.

To export a symbol, you must mark it with an annotation.
Cupcake [generates][1] a header on the include path, `{library}/export.hpp`,
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
It is called the **selection**.
The default selection is `release`,
it can be overridden with the `--flavor` option,
and any explicit override will be saved in the configuration file.


## `test`

Tests for the project are in the `tests` subdirectory.
A **test** is what CTest calls a test:
an executable that returns 0 if and only if it passed.

The `tests` subdirectory is included in the CMake project
only when tests are enabled,
i.e. when the CMake option `BUILD_TESTING` is on,
which it is by default.

You can build and execute tests with `cupcake test`.
This command will rebuild tests if their sources have changed.


## Dependencies

You can add a dependency with `cupcake add`.
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
cupcake search boost/1.81.0
```

We can try adding a dependency on libxrpl,
but chances are that it is not in your local cache,
and it is not yet in `conancenter`, the default remote cache.
We can first add it to your local cache from a clone of the
[repository][rippled]:

```
conan export .
```

The Conan package is named `xrpl`.[^2]
Now you can add a dependency on it:

```
cupcake add xrpl
```

This just adds the package as a requirement in the Conan recipe.
Cupcake cannot assume which libraries, executables, or tests in your project
should link against which exports of the package.
You'll have to finish the job.
Open the root `CMakeLists.txt`
and add calls to `cupcake_find_package` and `target_link_libraries`:

```cmake
cupcake_find_package(xrpl 1.10.0)
target_link_libraries(seedgen::libseedgen PUBLIC xrpl::libxrpl)
```

Now that you've changed `conanfile.py` and `CMakeLists.txt`,
`cupcake build` will reconfigure the build system and rebuild the project.
You can include public headers from libxrpl and get to work.


## Packaging

Cupcake will publish a package to your local Conan cache with `cupcake pack`.

If your project is using the default Conan recipe generated by `cupcake new`,
then the package step is equivalent to an installation.
Further, if your project's `CMakeLists.txt` calls `cupcake_install_cpp_info`,
then an installation will install Conan package information (`cpp_info.py`)
to be ingested by the recipe.

After packing `seedgen`, it is ready to use in another project:

- Create a second project with `cupcake new`.
- Add `seedgen` as a dependency with `cupcake add`.
- Link the library to `libseedgen` in the root `CMakeLists.txt`.
- Edit the library to use `libseedgen`.
- Edit the executable to use the library.
- Edit the test to test the library.
- Test and install.


[^1]: See [project-template-cpp] for an explanation of the constraints on
    a Cupcake project and the reasons for them.
[^2]: Maybe one day we'll be able to rename the GitHub project and executable
    to match.

[try-cupcake]: https://github.com/thejohnfreeman/try-cupcake
[project-template-cpp]: https://github.com/thejohnfreeman/project-template-cpp
[rippled]: https://github.com/XRPLF/rippled.git
[Cupcake]: https://pypi.org/project/cupcake/
[`cupcake`]: https://github.com/thejohnfreeman/project-template-cpp/tree/master/cupcake
[`doctest`]: https://github.com/doctest/doctest
[Conan]: https://conan.io/
[libxrpl]: https://github.com/XRPLF/rippled/blob/develop/conanfile.py#L146-L154
[`ripple::Seed`]: https://xrplf.github.io/rippled/classripple_1_1Seed.html
[`GNUInstallDirs`]: https://cmake.org/cmake/help/latest/module/GNUInstallDirs.html
[runtime]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#id31
[library]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#id32
[archive]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#id33
[PCF]: https://cmake.org/cmake/help/latest/manual/cmake-packages.7.html#package-layout
[Redirectory]: https://github.com/thejohnfreeman/redirectory

[1]: https://cmake.org/cmake/help/latest/module/GenerateExportHeader.html
[2]: https://cmake.org/cmake/help/latest/prop_tgt/MSVC_RUNTIME_LIBRARY.html
[3]: https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html#build-configurations
[4]: https://cmake.org/cmake/help/latest/manual/cmake-generators.7.html
[5]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/seedgen/src/libseedgen.cpp
[6]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/seedgen/include/seedgen/seedgen.hpp
[7]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/seedgen/src/seedgen.cpp
[8]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/seedgen/tests/seedgen.cpp
[9]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/seedgen/CMakeLists.txt
[10]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/seedgen/conanfile.py
[11]: https://github.com/thejohnfreeman/try-cupcake/blob/01-create/seedgen/.gitignore
