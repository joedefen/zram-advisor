"""zram-advisor: evaluate, tune, and configure zRAM on Linux."""

# The one place the release number lives.  pyproject.toml declares
# `dynamic = ["version"]`, so flit reads this line, `bless` reads it without
# importing the package, and `zram-advisor --version` prints it.
__version__ = "1.1.7"
