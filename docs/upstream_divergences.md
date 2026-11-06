# Upstream divergences

## Sync: upstream master -> feature/symc-upstream-pi-changes

### Commit b3d4b9e
small fixes and updates

Status:
Partially rejected

Files retained from local fork:

- webdaemon/templates/scan.html
- webdaemon/static/js/scan.js
- webdaemon/templates/settleplate.html
- webdaemon/templates/imageoverlay.html

Reason:

The local implementation contains deployment-specific behavior:

- TensorFlow-based colony detection support is retained.
- Image zoom synchronization is retained.
- Defensive image placeholder handling is retained.
- Existing scan workflow improvements are retained.

Accepted upstream changes:

- camera and illumination updates
- hwlog.py rename
- exposure/gain handling improvements
- cleanup session removal (Redis-based handling)