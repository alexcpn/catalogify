"""catalogify — turn a repository into a knowledge catalog an agent can afford to read.

Generates an Open Knowledge Format (OKF v0.1) bundle: cross-linked markdown
concepts with YAML frontmatter describing a codebase's services, modules, APIs,
data models and operations. Mines git history for the reasoning behind the code,
and parks what it cannot establish as an open question rather than inventing it.

OKF spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

__version__ = "0.5.0"
