#!/bin/bash
# Regenerate SDK reference docs from Python docstrings.
# Run this after changing any public class/method docstrings.
#
# Requires: pip install pydoc-markdown
# Output: docs/server.md, docs/events.md, docs/client.md
#
# These generated docs are consumed by the Docusaurus build script
# (content/IP-camera-API/docusaurus/build-docs.sh) which adds
# frontmatter and copies them into the API docs tree.

cd "$(dirname "$0")"
mkdir -p docs

echo "Generating SDK reference docs..."

pydoc-markdown -m viewtron.server -I src --render-toc > docs/server.md
echo "  docs/server.md"

pydoc-markdown -m viewtron.events -I src --render-toc > docs/events.md
echo "  docs/events.md"

pydoc-markdown -m viewtron.client -I src --render-toc > docs/client.md
echo "  docs/client.md"

echo "Done. Commit and push, then rebuild Docusaurus."
