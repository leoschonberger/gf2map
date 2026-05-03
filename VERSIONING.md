# Versioning Strategy

This project uses semantic versioning with automatic patch version incrementation.

## How It Works

### Automatic Patch Versioning
- The [VERSION](VERSION) file contains the base version (e.g., `0.1.0`)
- On every commit to `main`, the patch number is automatically set to the total commit count
- Example: With base version `0.1.0` and 42 commits, the built version will be `0.1.42`

### Manual Major/Minor Versioning
To bump the major or minor version:

1. Update the [VERSION](VERSION) file manually:
   ```bash
   echo "1.0.0" > VERSION
   git add VERSION
   git commit -m "Bump version to 1.0.0"
   ```

2. Optionally create a git tag for the release:
   ```bash
   git tag v1.0.0
   git push origin main
   git push origin v1.0.0
   ```

## Docker Image Tags

Every build creates these tags:
- `latest` - always points to the latest main branch build
- `main` - tracks the main branch
- `0.1.42` - specific version number (auto-generated from commit count)
- `main-sha123abc` - git commit SHA for exact reference

When you create a version tag (e.g., `v1.0.0`), additional tags are created:
- `1.0.0` - full version
- `1.0` - minor version
- `1` - major version

## Examples

### Check Current Version
```bash
docker inspect ghcr.io/leoschonberger/gf2map:latest | grep version
```

### Use a Specific Version
```yaml
# docker-compose.prod.yml
services:
  app:
    image: ghcr.io/leoschonberger/gf2map:0.1.42
```

### Bump to Version 1.0.0
```bash
echo "1.0.0" > VERSION
git add VERSION
git commit -m "Release version 1.0.0"
git tag v1.0.0
git push origin main --tags
```

After this, all future commits will be versioned as `1.0.X` where X is the commit count.
