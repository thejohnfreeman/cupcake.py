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
--------

To use this tool, your C++ project must fit a certain profile and follow some
conventions. The profile is what I call a **basic C++ project**:

- A **name** that is a valid C++ identifier.
- Some **public headers** nested under a directory named after the project.
- One **library**, named after the project, that can be linked statically or
  dynamically (with no other options).
- Zero or more **executables** that depend on the library.

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


Etymology
---------

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
