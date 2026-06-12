# Vendored assets

## axe-core

`axe.min.js` is axe-core v4.10.2, downloaded from jsDelivr on 2026-06-12:

```
curl -sSL -o axe.min.js https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js
```

License: MPL-2.0 (Deque Systems). Source: <https://github.com/dequelabs/axe-core>.

We vendor rather than fetch at runtime so audits are reproducible and
network-isolated. To upgrade, replace the file and bump the version note.
