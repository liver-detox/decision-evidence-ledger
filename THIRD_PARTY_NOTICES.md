# Third-Party Notices

## Distributed runtime

Runtime dependencies: none. The project imports only Python standard-library
modules, which are not redistributed by this project.

No third-party code, data, media, font, or binary is vendored in this local
candidate.

## Local build tooling

The package declares `setuptools>=77` as its build backend requirement so that
the SPDX license expression and license-file metadata follow PEP 639. The
local offline build rehearsal used setuptools 83.0.0, whose installed package
metadata identifies its license as MIT.

Build tools are not runtime dependencies and are not bundled into the wheel.
Any future release must recheck the actual build environment and update this
inventory if the tool or license changes.

## Referenced CI actions

The local-only workflow references, but does not vendor or include in the
wheel or source distribution, `actions/checkout` v7.0.1 at immutable commit
`3d3c42e5aac5ba805825da76410c181273ba90b1` and `actions/setup-python` v7.0.0
at immutable commit `5fda3b95a4ea91299a34e894583c3862153e4b97`. The reviewed
upstream action releases are MIT licensed. These references remain inactive
until an authorized push, and their versions, commits, licenses, and hosted
behavior must be rechecked before the first run.
