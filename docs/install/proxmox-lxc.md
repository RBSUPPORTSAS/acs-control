# ACS Control en Proxmox VE (contenedor LXC)

Un contenedor LXC con Debian 13 es la forma más liviana de correr ACS Control en Proxmox.
No necesita Docker ni privilegios especiales.

> Estado: **por validar**. Si la sigue, reporte el resultado para actualizar
> [la tabla de plataformas](../INSTALL.md).

## 1. Descargar la plantilla de Debian 13

En el nodo de Proxmox (shell del host):

```bash
pveam update
pveam available --section system | grep debian-13
```

Descargue la plantilla que aparezca en la lista (el nombre exacto cambia con cada versión):

```bash
pveam download local debian-13-standard_<VERSION>_amd64.tar.zst
```

## 2. Crear el contenedor

Ajuste el ID (`210`), el almacenamiento (`local-lvm`), el bridge (`vmbr0`) y la red
según su entorno:

```bash
pct create 210 local:vztmpl/debian-13-standard_<VERSION>_amd64.tar.zst \
  --hostname acs-control \
  --cores 2 \
  --memory 2048 \
  --swap 512 \
  --rootfs local-lvm:10 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1 \
  --onboot 1 \
  --timezone America/Bogota

pct start 210
pct enter 210
```

- `--unprivileged 1`: ACS Control no necesita un contenedor privilegiado.
- `--features nesting=1`: recomendado para que systemd funcione bien en Debian 12+.
- Para IP fija use `ip=192.0.2.50/24,gw=192.0.2.1` en lugar de `ip=dhcp`.

También puede crearlo desde la interfaz web (**Create CT**) con los mismos valores.

## 3. Verificar acceso a GenieACS

Antes de instalar, confirme que el contenedor llega al NBI de GenieACS:

```bash
apt update && apt install -y curl
curl -s -o /dev/null -w '%{http_code}\n' "http://GENIEACS_SERVER:7557/devices/?projection=_id&limit=1"
```

Debe responder `200`. Si GenieACS está en otra red (por ejemplo detrás de una VPN), el
contenedor necesita una ruta hacia ella: la VPN debe terminar en el router o en el host
de Proxmox, no solo en el equipo de un operador.

## 4. Instalar ACS Control

Dentro del contenedor, siga la [guía de Linux](linux.md) desde el paso 1. Debian 13
trae Python y Node.js en versiones compatibles, así que no necesita pasos adicionales.

## 5. Recomendaciones para producción

- **Copias de seguridad:** programe un backup del contenedor en
  *Datacenter → Backup* (vzdump, modo snapshot).
- **Snapshot antes de actualizar:** `pct snapshot 210 antes-de-actualizar`
  y, si algo falla, `pct rollback 210 antes-de-actualizar`.
- **Firewall de Proxmox:** permita el puerto 80 solo desde la red de operadores del NOC.
- **Arranque automático:** `--onboot 1` hace que el contenedor inicie con el nodo.

## Problemas comunes

### Avisos de `locale` al instalar paquetes

```bash
apt install -y locales
dpkg-reconfigure locales   # elija es_CO.UTF-8 o en_US.UTF-8
```

### `systemctl` falla dentro del contenedor

Verifique que el contenedor tenga `nesting=1`:

```bash
pct set 210 --features nesting=1   # en el host, con el contenedor detenido
```
