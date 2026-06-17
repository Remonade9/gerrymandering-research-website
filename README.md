# Gerrymandering Research — Website

Companion website presenting the findings of Lucas's applied mathematics / GIS
research on detecting partisan gerrymandering using Markov Chain Monte Carlo
(MCMC) simulation. Mentored by Prof. Bo Zhao, Humanistic GIS Lab, University of
Washington.

## Structure

- `index.html` — single-page site (abstract, background, methods, maps, findings)
- `styles.css` — styling

## Viewing locally

Just open `index.html` in a browser. No build step required.

To serve it with live reload (optional), from this folder run:

```sh
python -m http.server 8000
```

then visit <http://localhost:8000>.

## Publishing

This is a static site. When ready to publish, it can be deployed for free via
**GitHub Pages** (requires the repository to be public, or a paid plan for
private repos): Settings → Pages → Deploy from branch → `main` / root.
