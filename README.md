# CD Factu (Linux)

Programa de facturación sencilla para autónomos y micropymes, con integración de **Verifactu**.
Esta es la versión para **Linux** (código fuente + ejecutable AppImage). No requiere Windows ni Wine.

## Requisitos del sistema (Linux)
- Distribución Linux de 64 bits (probado en Ubuntu 22.04+ y derivados).
- Para el AppImage: `libfuse2` instalada:
  ```bash
  # Debian/Ubuntu
  sudo apt install libfuse2
  # Fedora
  sudo dnf install fuse-libs
  # Arch
  sudo pacman -S fuse2
  ```
- Para ejecutar desde código fuente: Python 3.10+ y las librerías del sistema que exige PySide6 (libxcb, libxkbcommon, libgl, etc.):
  ```bash
  # Debian/Ubuntu
  sudo apt install python3 python3-pip libxcb-cursor0 libxkbcommon-x11-0 libgl1
  ```

## Características principales
- Interfaz sencilla, botones grandes y tema oscuro.
- Gestión de empresa, clientes, productos y facturas.
- Emisión de facturas en PDF con código QR Verifactu.
- Control de cobros y estado de pago.
- Anulación/rectificación de facturas (sin borrar).
- Copia de seguridad y restauración de datos.
- Funciona sin conexión a internet (datos locales).


## Capturas de pantalla

### Menú principal
![Menú principal](docs/screenshots/01_menu_principal.png)

### Mis datos de empresa
![Mis datos de empresa](docs/screenshots/02_datos_empresa.png)

### Clientes
![Clientes](docs/screenshots/03_clientes.png)

### Productos
![Productos](docs/screenshots/04_productos.png)

### Emitir factura
![Emitir factura](docs/screenshots/05_emitir_factura.png)

### Facturas emitidas
![Facturas emitidas](docs/screenshots/06_facturas_emitidas.png)

### Certificado Verifactu
![Certificado Verifactu](docs/screenshots/07_certificado_verifactu.png)

### Factura generada (PDF)
![Factura generada](docs/screenshots/08_factura_ejemplo.png)

## Instalación

### Opción 1: AppImage (recomendado, sin instalación)
1. Descarga `CD-Factu-x86_64.AppImage` desde la sección **Releases**.
2. Dale permisos de ejecución:
   ```bash
   chmod +x CD-Factu-x86_64.AppImage
   ```
3. Ejecútalo con doble clic o desde la terminal:
   ```bash
   ./CD-Factu-x86_64.AppImage
   ```

### Opción 2: Desde código fuente
Requisitos: Python 3.10+ y las dependencias de `requirements.txt` (PySide6, reportlab, qrcode, Pillow).

```bash
git clone https://github.com/davidcasascompetenciadigital-prog/CD-Factu-Linux.git
cd CD-Factu-Linux
pip install -r requirements.txt
python3 main.py
```

### Opción 3: Compilar ejecutable
```bash
pip install pyinstaller
bash build-appimage.sh
```

## Uso
1. Ejecuta el programa (se crea la base de datos automáticamente en `~/.local/share/CD Factu/`).
2. Rellena "Mis datos de empresa" (con ayuda de tu asesor si es necesario).
3. Añade clientes y productos.
4. Emite facturas desde "Emitir factura".
5. Consulta e imprime en "Facturas emitidas".

Los datos se guardan en `~/.local/share/CD Factu/` y las copias de seguridad en `~/Desktop/Backup_Facturas` (o en `$HOME` si no existe el Escritorio).

## Verifactu
Modalidad local: no requiere certificado por parte del usuario final. Configuración opcional de certificado (prueba/real) en "Mis datos de empresa".

## Licencia
Creative Commons Compartir Igual Mención (CC BY-SA). Software GRATUITO.

## Autor
David Casas M.
- YouTube: @Competencia_Digital
- Twitch: davidcasasm
- GitHub: davidcasascompetenciadigital-prog
