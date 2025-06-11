#!/bin/bash
# Script to set up APT repository for Eir

set -e

REPO_DIR="apt-repo"
DIST="stable"
COMPONENT="main"
ARCH="amd64"

echo "Setting up APT repository..."

# Create repository structure
mkdir -p ${REPO_DIR}/dists/${DIST}/${COMPONENT}/binary-${ARCH}
mkdir -p ${REPO_DIR}/pool/${COMPONENT}

# Copy .deb file to pool
if [ -f "packages/eir_"*"_amd64.deb" ]; then
    cp packages/eir_*_amd64.deb ${REPO_DIR}/pool/${COMPONENT}/
    echo "Copied .deb file to repository pool"
else
    echo "Error: No .deb file found in packages/ directory"
    exit 1
fi

# Generate Packages file
cd ${REPO_DIR}
dpkg-scanpackages pool/${COMPONENT} /dev/null > dists/${DIST}/${COMPONENT}/binary-${ARCH}/Packages

# Compress Packages file
gzip -c dists/${DIST}/${COMPONENT}/binary-${ARCH}/Packages > dists/${DIST}/${COMPONENT}/binary-${ARCH}/Packages.gz

# Create Release file
cd dists/${DIST}

cat > Release << EOF
Origin: Eir Repository
Label: Eir
Suite: ${DIST}
Codename: ${DIST}
Version: 1.0
Architectures: ${ARCH}
Components: ${COMPONENT}
Description: EXIF-based image renamer and RAW format converter
Date: $(date -u '+%a, %d %b %Y %H:%M:%S UTC')
EOF

# Generate checksums for Release file
echo "MD5Sum:" >> Release
find . -name "Packages*" | xargs md5sum | sed 's|\./||' | awk '{print " " $1 " " $2}' >> Release

echo "SHA1:" >> Release
find . -name "Packages*" | xargs sha1sum | sed 's|\./||' | awk '{print " " $1 " " $2}' >> Release

echo "SHA256:" >> Release
find . -name "Packages*" | xargs sha256sum | sed 's|\./||' | awk '{print " " $1 " " $2}' >> Release

cd ../..

echo "APT repository created successfully in ${REPO_DIR}/"
echo ""
echo "To use this repository, users should:"
echo "1. Add the repository:"
echo "   echo 'deb [trusted=yes] https://yourdomain.com/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/eir.list"
echo "2. Update package list:"
echo "   sudo apt update"
echo "3. Install eir:"
echo "   sudo apt install eir"