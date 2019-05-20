.. start-include

=======
cupcake
=======

Make C++ a piece of cake.

.. image:: https://travis-ci.org/thejohnfreeman/cupcake.svg?branch=master
   :target: https://travis-ci.org/thejohnfreeman/cupcake
   :alt: Build status

.. image:: https://readthedocs.org/projects/cupcake/badge/?version=latest
   :target: https://cupcake.readthedocs.io/
   :alt: Documentation status

.. image:: https://img.shields.io/pypi/v/cupcake.svg
   :target: https://pypi.org/project/cupcake/
   :alt: Latest PyPI version

.. image:: https://img.shields.io/pypi/pyversions/cupcake.svg
   :target: https://pypi.org/project/cupcake/
   :alt: Python versions supported

Cupcake is a thin layer over CMake_ and Conan_ that tries to offer
a better user experience in the style of Yarn_ or Poetry_.

.. _CMake: https://cmake.org/cmake/help/latest/manual/cmake.1.html
.. _Conan: https://docs.conan.io/
.. _Yarn: https://yarnpkg.com/en/
.. _Poetry: https://poetry.eustace.io/


Audience
========

To use this tool, your C++ project must fit a certain profile and follow some
conventions. The profile is what I call a **basic C++ project**:

- A **name** that is a valid C++ identifier.
- Zero or more **public dependencies**. These may be runtime dependencies of
  the library or executables, or they may be build time dependencies of the
  public headers. Users must install the public dependencies when they install
  the project.
- Some **public headers** nested under a directory named after the project.
- One **library**, named after the project, that can be linked statically or
  dynamically (with no other options). The library depends on the public
  headers and the public dependencies.
- Zero or more **executables** that depend on the public headers, the library,
  and the public dependencies.
- Zero or more **private dependencies**. These are often test frameworks.
  Developers working on the library expect them to be installed, but users of
  the library do not.
- Zero or more **tests** that depend on the public headers, the library, the
  public dependencies, and the private dependencies.

The conventions are popular in the community and seem to be considered__
best__ practices__:

.. __: https://www.youtube.com/watch?v=eC9-iRN2b04
.. __: https://pabloariasal.github.io/2018/02/19/its-time-to-do-cmake-right/
.. __: https://unclejimbo.github.io/2018/06/08/Modern-CMake-for-Library-Developers/

- The project is built and installed with **CMake** [#]_.
- The project uses **semantic versioning**.
- The project installs itself relative to a **prefix**. Public headers are
  installed in ``include/``; static and dynamic libraries are installed in
  ``lib/``; executables are installed in ``bin/``.
- The project installs a `CMake package configuration file`__ that exports
  a target for the library. The target is named after the project, and it is
  scoped within a namespace named after the project. Dependents link against
  that target with the **same syntax** whether it was installed with CMake or
  with Conan.

.. __: https://cmake.org/cmake/help/latest/manual/cmake-packages.7.html#package-configuration-file


Commands
========

``package``
-----------

This abstracts the ``conan create`` `↗️`__ command. It:

.. __: https://docs.conan.io/en/latest/reference/commands/creator/create.html

- Copies a Conan recipe for your project to your local Conan cache, a la
  ``conan export`` `↗️`__.

   .. __: https://docs.conan.io/en/latest/reference/commands/creator/export.html

- Builds the recipe for your current settings (CPU architecture, operating
  system, compiler) and the ``Release`` build type, a la ``conan install``
  `↗️`__.

   .. __: https://docs.conan.io/en/latest/reference/commands/consumer/install.html

- Configures and builds an example that depends on your project as a test of
  its packaging, a la ``conan
  test`` `↗️`__. That example must reside in the ``example/`` directory of your
  project with a ``CMakeLists.txt`` that looks like this:

   .. __: https://docs.conan.io/en/latest/reference/commands/creator/test.html

   .. code-block:: cmake

      add_executable(example example.cpp)
      target_link_libraries(example ${PROJECT_NAME}::${PROJECT_NAME})

  .. TODO: example.cpp in place of example/ directory.


Etymology
=========

I love Make_, but it's just not cross-platform. Just about every other
single letter prefix of "-ake" is taken, including the obvious candidate for
C++ (but stolen by C#), Cake_. From there, it's a small step to Cppcake,
which needs an easy pronunciation. "Cupcake" works. I prefer names to be
spelled with an unambiguous pronunciation so that readers are not left
confused, so I might as well name the tool Cupcake. A brief `Google
search`__ appears to confirm
the name is unclaimed in the C++ community.

.. _Make: https://www.gnu.org/software/make/
.. _Cake: https://cakebuild.net/
.. __: https://www.google.com/search?q=c%2B%2B+cupcake


.. [#] CMake likes to remind everyone that it is a build system *generator*,
   not a build system, but it is reaching a level of abstraction that lets
   us think of it as a cross-platform build system.

.. end-include
