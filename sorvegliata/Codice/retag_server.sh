#!/bin/bash
# Retag immagini trama importate con nomi versionati per i deployment k8s
# Uso: ./retag_server.sh 1.2.7

MK=/var/lib/snapd/snap/bin/microk8s

if [ -z "$1" ]; then
    echo "Uso: $0 <versione>  es: $0 1.2.7"
    exit 1
fi

VERSION=$1

tag() {
    src=$1
    dst=$2
    echo "--> $src"
    echo "    => $dst"
    sudo $MK ctr images tag "$src" "$dst" && echo "    OK" || echo "    ERRORE"
}

tag "docker.io/trama/sgw:latest"                   "docker.io/library/sgw:${VERSION}"
tag "docker.io/trama/sdm:latest"                   "docker.io/library/sdm:${VERSION}"
tag "docker.io/library/trama-mtc:latest"            "docker.io/library/mtc:${VERSION}"
tag "docker.io/library/trama-ttm:latest"            "docker.io/library/ttm:${VERSION}"
tag "docker.io/library/trama-nxvalidator:latest"    "docker.io/library/nxvalidator:${VERSION}"
tag "docker.io/library/trama-hci-manager:latest"    "docker.io/library/hci-manager:${VERSION}"
tag "docker.io/library/trama-hci-rest-api:latest"   "docker.io/library/hci-rest-api:${VERSION}"
tag "docker.io/library/trama-datawriter:latest"     "docker.io/library/datawriter:${VERSION}"
tag "docker.io/library/trama-redis:latest"          "docker.io/library/trama-redis:${VERSION}"

echo ""
echo "=== Immagini con tag ${VERSION} ==="
sudo $MK ctr images ls | grep ":${VERSION}" | awk '{print $1}'
