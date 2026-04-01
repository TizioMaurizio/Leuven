# Diagrams — Week 1

This directory is reserved for exported diagram images (SVG/PNG) when needed as fallbacks for environments that do not render Mermaid.

All diagrams are embedded directly in the Markdown files as Mermaid code blocks, which GitHub renders natively. If you need static images:

1. Run the [interactive demos](../../interactive/week1/) with `--draw` flag where supported
2. Use the [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) to export diagrams from Markdown

```bash
# Example: export a Mermaid diagram to SVG
npx @mermaid-js/mermaid-cli -i input.mmd -o output.svg
```
