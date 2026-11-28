# app/ui/tab_empresa.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QComboBox, QPushButton, QFileDialog, QMessageBox, QCheckBox,
                               QStackedWidget, QTextEdit, QFrame, QScrollArea)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from ..db.database import get_connection
from ..ui.widgets import big_button, title_label, help_popup, info, error
from ..utils.messages import MSG_FALTA_NIF_EMPRESA, ayuda
from ..utils.validators import validar_nif_cif, normalizar_dni, normalizar_cif, validar_dni, validar_cif
from ..config import LOGO_DIR

COMUNIDADES = ["Andalucía","Aragón","Asturias","Baleares","Canarias","Cantabria",
               "Castilla-La Mancha","Castilla y León","Cataluña","Extremadura",
               "Galicia","Madrid","Murcia","Navarra","País Vasco","La Rioja","Ceuta","Melilla"]

EXPLICACIONES = {
    "Datos de empresa": "Rellena los datos de tu negocio: nombre, NIF/CIF, dirección, etc. "
                        "Se usarán en todas tus facturas.",
    "Notas": "Anota aquí recordatorios internos de tu empresa (no aparecen en las facturas).",
    "Datos Verifactu": "Configura el envío de facturas a la Agencia Tributaria (Verifactu). "
                       "Es opcional; si no activas, tus facturas se guardan solo en local.",
}


class TabEmpresa(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        v = QVBoxLayout(self)
        v.setSpacing(12)
        v.addWidget(title_label("Mis datos de empresa"))

        # --- Submenú ---
        submenu = QHBoxLayout()
        submenu.setSpacing(12)
        submenu.addStretch()
        self.btns_submenu = {}
        self.pages = QStackedWidget()
        for nombre in ("Datos de empresa", "Notas", "Datos Verifactu"):
            col = QVBoxLayout()
            col.setSpacing(4)
            b = big_button(nombre, "secondary")
            b.setFixedWidth(160)
            b.setFixedHeight(36)
            b.setStyleSheet(b.styleSheet() + "font-size:12px;")
            b.clicked.connect(lambda checked=False, n=nombre: self._cambiar_pagina(n))
            col.addWidget(b, alignment=Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel(EXPLICACIONES[nombre])
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size:10px; color:#aaaaaa;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(170)
            col.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            submenu.addLayout(col)
            self.btns_submenu[nombre] = b
        submenu.addStretch()
        v.addLayout(submenu)

        # --- Página 1: Datos de empresa ---
        page1 = QWidget()
        p1 = QHBoxLayout(page1)
        p1.setSpacing(16)

        # Columna izquierda
        left = QVBoxLayout()
        left.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(QLabel("Nombre o razón social:"))
        self.inp_nombre = QLineEdit()
        row.addWidget(self.inp_nombre)
        left.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("NIF/CIF:"))
        self.inp_nif = QLineEdit()
        self.inp_nif.textChanged.connect(self._validar_nif)
        self.inp_nif.editingFinished.connect(self._normalizar_nif)
        row.addWidget(self.inp_nif)
        self.lbl_nif_status = QLabel("")
        row.addWidget(self.lbl_nif_status)
        left.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Dirección:"))
        self.inp_dir = QLineEdit()
        row.addWidget(self.inp_dir)
        left.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Código Postal:"))
        self.inp_cp = QLineEdit()
        row.addWidget(self.inp_cp)
        left.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Ciudad:"))
        self.inp_ciudad = QLineEdit()
        row.addWidget(self.inp_ciudad)
        left.addLayout(row)

        left.addStretch()

        # Columna derecha
        right = QVBoxLayout()
        right.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(QLabel("Comunidad Autónoma:"))
        self.cmb_ccaa = QComboBox()
        self.cmb_ccaa.addItems(COMUNIDADES)
        row.addWidget(self.cmb_ccaa)
        right.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("País:"))
        self.inp_pais = QLineEdit("España")
        row.addWidget(self.inp_pais)
        right.addLayout(row)

        # Logotipo
        row = QHBoxLayout()
        self.lbl_logo = QLabel("Sin logotipo")
        self.lbl_logo.setFixedSize(120, 60)
        self.lbl_logo.setStyleSheet("border:1px solid #bdbdbd; background:#fff;")
        row.addWidget(self.lbl_logo)
        btn_logo = big_button("Elegir logotipo", "secondary")
        btn_logo.clicked.connect(self.elegir_logo)
        row.addWidget(btn_logo)
        row.addStretch()
        right.addLayout(row)
        self.logo_path = None

        # Tipos de IVA
        right.addWidget(QLabel("Tipos de IVA (separados por coma, ej: 21,10,4,0):"))
        self.inp_iva = QLineEdit("21,10,4,0")
        right.addLayout(self._wrap(self.inp_iva))

        # Recargo de equivalencia
        self.chk_recargo = QCheckBox("Activar recargo de equivalencia (comercio minorista)")
        right.addWidget(self.chk_recargo)

        # Registro Mercantil
        row = QHBoxLayout()
        row.addWidget(QLabel("Registro Mercantil:"))
        self.inp_registro = QLineEdit()
        row.addWidget(self.inp_registro)
        right.addLayout(row)

        right.addStretch()

        p1.addLayout(left, 1)
        p1.addLayout(right, 1)
        self.pages.addWidget(page1)

        # --- Página 2: Notas ---
        page2 = QWidget()
        p2 = QVBoxLayout(page2)
        p2.addWidget(QLabel("Notas internas de la empresa:"))
        self.inp_notas = QTextEdit()
        self.inp_notas.setPlaceholderText("Anota aquí recordatorios internos. No aparecen en las facturas.")
        p2.addWidget(self.inp_notas)
        p2.addStretch()
        self.pages.addWidget(page2)

        # --- Página 3: Datos Verifactu (dos columnas) ---
        page3 = QWidget()
        p3 = QHBoxLayout(page3)
        p3.setSpacing(16)

        # Columna izquierda: configuración
        left = QVBoxLayout()
        left.addWidget(QLabel("Configuración Verifactu (opcional):"))
        row = QHBoxLayout()
        self.chk_verifactu = QCheckBox("Activar Verifactu")
        row.addWidget(self.chk_verifactu)
        row.addWidget(QLabel("Modo:"))
        self.cmb_vf_mode = QComboBox()
        self.cmb_vf_mode.addItems(["Prueba (preproducción)", "Real (producción)"])
        row.addWidget(self.cmb_vf_mode)
        row.addStretch()
        left.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Certificado público (.crt/.cer):"))
        self.inp_vf_cert = QLineEdit()
        row.addWidget(self.inp_vf_cert)
        btn_cert = big_button("Elegir", "secondary")
        btn_cert.setFixedWidth(100)
        btn_cert.clicked.connect(lambda: self.elegir_archivo(self.inp_vf_cert, "Certificado (*.crt *.cer *.pem)"))
        row.addWidget(btn_cert)
        left.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Clave privada (.key/.pem):"))
        self.inp_vf_key = QLineEdit()
        row.addWidget(self.inp_vf_key)
        btn_key = big_button("Elegir", "secondary")
        btn_key.setFixedWidth(100)
        btn_key.clicked.connect(lambda: self.elegir_archivo(self.inp_vf_key, "Clave privada (*.key *.pem)"))
        row.addWidget(btn_key)
        left.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Contraseña del certificado:"))
        self.inp_vf_pass = QLineEdit()
        self.inp_vf_pass.setEchoMode(QLineEdit.EchoMode.Password)
        row.addWidget(self.inp_vf_pass)
        left.addLayout(row)

        lbl_doc = QLabel('<a href="https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/informacion-tecnica.html" style="color:#4caf50;">Documentación técnica Verifactu (AEAT)</a>')
        lbl_doc.setOpenExternalLinks(True)
        left.addWidget(lbl_doc)
        left.addStretch()

        # Columna derecha: explicación
        right = QVBoxLayout()
        info_box = QFrame()
        info_box.setStyleSheet("background:#1e1e1e; border:1px solid #3a3a3a; border-radius:10px;")
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(14, 14, 14, 14)
        titulo = QLabel("¿Qué es Verifactu?")
        titulo.setStyleSheet("font-size:16px; font-weight:bold; color:#4caf50;")
        info_layout.addWidget(titulo)
        texto = QLabel(
            "Verifactu es el sistema de la Agencia Tributaria (AEAT) para que las facturas "
            "se registren de forma segura e inalterable. Cuando lo activas, cada factura "
            "genera un código QR que el cliente puede verificar en la web de Hacienda.\n\n"
            "Es opcional: si no lo activas, tus facturas se guardan solo en tu ordenador.\n\n"
            "¿Cómo añadir la firma digital?\n"
            "1. Pide a tu asesor o a la AEAT el certificado digital de tu empresa "
            "(un archivo .crt o .cer) y su clave privada (.key).\n"
            "2. Pulsa \"Elegir\" junto a \"Certificado público\" y selecciona el archivo .crt/.cer.\n"
            "3. Pulsa \"Elegir\" junto a \"Clave privada\" y selecciona el archivo .key.\n"
            "4. Escribe la contraseña del certificado en el campo \"Contraseña\".\n"
            "5. Marca \"Activar Verifactu\" y elige modo \"Prueba\" para probar primero.\n"
            "6. Pulsa \"GUARDAR DATOS\".\n\n"
            "Si no tienes certificado, deja Verifactu desactivado: el programa funciona igual "
            "y genera facturas válidas en PDF."
        )
        texto.setWordWrap(True)
        texto.setStyleSheet("font-size:13px; color:#dddddd;")
        info_layout.addWidget(texto)
        info_layout.addStretch()
        right.addWidget(info_box)
        right.addStretch()

        p3.addLayout(left, 1)
        p3.addLayout(right, 1)
        self.pages.addWidget(page3)

        v.addWidget(self.pages)

        # Botones
        row = QHBoxLayout()
        btn_guardar = big_button("GUARDAR", "primary")
        btn_guardar.clicked.connect(self.guardar)
        row.addWidget(btn_guardar)
        btn_help = big_button("?", "secondary")
        btn_help.setFixedWidth(60)
        btn_help.clicked.connect(lambda: help_popup(self, ayuda("empresa")))
        row.addWidget(btn_help)
        row.addStretch()
        v.addLayout(row)
        v.addStretch()

        self._cambiar_pagina("Datos de empresa")
        self.cargar()

    def _wrap(self, w):
        h = QHBoxLayout()
        h.addWidget(w)
        return h

    def _cambiar_pagina(self, nombre):
        idx = {"Datos de empresa": 0, "Notas": 1, "Datos Verifactu": 2}[nombre]
        self.pages.setCurrentIndex(idx)
        for n, b in self.btns_submenu.items():
            if n == nombre:
                b.setStyleSheet("")  # default primary-ish
            else:
                pass

    def _validar_nif(self, texto):
        t = (texto or "").strip()
        if not t:
            self.lbl_nif_status.setText("")
            self.inp_nif.setStyleSheet("")
            return
        if validar_nif_cif(t):
            self.lbl_nif_status.setText("✓")
            self.lbl_nif_status.setStyleSheet("color:#4caf50; font-weight:bold;")
            self.inp_nif.setStyleSheet("border:2px solid #4caf50;")
        else:
            self.lbl_nif_status.setText("Revisa")
            self.lbl_nif_status.setStyleSheet("color:#e53935; font-weight:bold;")
            self.inp_nif.setStyleSheet("border:2px solid #e53935;")

    def _normalizar_nif(self):
        t = self.inp_nif.text().strip().upper()
        if len(t) == 8 and t.isdigit():
            self.inp_nif.setText(normalizar_dni(t))
        elif len(t) == 8 and t[0].isalpha() and t[1:].isdigit():
            self.inp_nif.setText(normalizar_cif(t))

    def elegir_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Elegir logotipo", "", "Imágenes (*.png *.jpg *.jpeg)")
        if path:
            self.logo_path = path
            pix = QPixmap(path).scaled(120, 60)
            self.lbl_logo.setPixmap(pix)

    def cargar(self):
        conn = get_connection()
        r = conn.execute("SELECT * FROM empresa WHERE id=1").fetchone()
        if r:
            self.inp_nombre.setText(r["nombre"] or "")
            self.inp_nif.setText(r["nif"] or "")
            self.inp_dir.setText(r["direccion"] or "")
            self.inp_cp.setText(r["cp"] or "")
            self.inp_ciudad.setText(r["ciudad"] or "")
            idx = self.cmb_ccaa.findText(r["comunidad_autonoma"] or "")
            if idx >= 0: self.cmb_ccaa.setCurrentIndex(idx)
            self.inp_pais.setText(r["pais"] or "España")
            self.inp_registro.setText((r["registro_mercantil"] or "") if "registro_mercantil" in r.keys() else "")
            if "notas" in r.keys():
                self.inp_notas.setPlainText(r["notas"] or "")
            if r["logo_path"]:
                self.logo_path = r["logo_path"]
                pix = QPixmap(r["logo_path"]).scaled(120, 60)
                self.lbl_logo.setPixmap(pix)
        ivas = conn.execute("SELECT porcentaje FROM tipos_iva WHERE activo=1 ORDER BY orden").fetchall()
        if ivas:
            self.inp_iva.setText(",".join(str(int(x["porcentaje"])) for x in ivas))
        # Recargo de equivalencia
        self.chk_recargo.setChecked(bool(r["recargo_equivalencia_enabled"]) if "recargo_equivalencia_enabled" in r.keys() else False)
        # Verifactu
        self.chk_verifactu.setChecked(bool(r["verifactu_enabled"]) if "verifactu_enabled" in r.keys() else False)
        mode = r["verifactu_mode"] if "verifactu_mode" in r.keys() else "prueba"
        self.cmb_vf_mode.setCurrentIndex(1 if mode == "real" else 0)
        self.inp_vf_cert.setText((r["verifactu_cert_path"] or "") if "verifactu_cert_path" in r.keys() else "")
        self.inp_vf_key.setText((r["verifactu_key_path"] or "") if "verifactu_key_path" in r.keys() else "")
        self.inp_vf_pass.setText((r["verifactu_cert_password"] or "") if "verifactu_cert_password" in r.keys() else "")
        conn.close()

    def elegir_archivo(self, inp, filtro):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", "", filtro)
        if path:
            inp.setText(path)

    def guardar(self):
        if not self.inp_nombre.text().strip():
            error(self, "Falta el nombre de la empresa. Escribe aquí: " + self.inp_nombre.placeholderText())
            self.inp_nombre.setFocus()
            return
        if not self.inp_nif.text().strip():
            error(self, MSG_FALTA_NIF_EMPRESA)
            self.inp_nif.setFocus()
            return
        conn = get_connection()
        mode = "real" if self.cmb_vf_mode.currentIndex() == 1 else "prueba"
        conn.execute("""UPDATE empresa SET nombre=?, nif=?, direccion=?, cp=?, ciudad=?,
                        comunidad_autonoma=?, pais=?, logo_path=?, verifactu_enabled=?, verifactu_mode=?,
                        verifactu_cert_path=?, verifactu_key_path=?, verifactu_cert_password=?,
                        registro_mercantil=?, notas=?, recargo_equivalencia_enabled=?,
                        actualizado_en=datetime('now','localtime') WHERE id=1""",
                    (self.inp_nombre.text().strip(), self.inp_nif.text().strip(),
                     self.inp_dir.text().strip(), self.inp_cp.text().strip(),
                     self.inp_ciudad.text().strip(), self.cmb_ccaa.currentText(),
                     self.inp_pais.text().strip(), self.logo_path,
                     1 if self.chk_verifactu.isChecked() else 0, mode,
                     self.inp_vf_cert.text().strip(), self.inp_vf_key.text().strip(),
                     self.inp_vf_pass.text(), self.inp_registro.text().strip(),
                     self.inp_notas.toPlainText().strip(),
                     1 if self.chk_recargo.isChecked() else 0))
        # Actualizar recargo_porcentaje en tipos_iva según activación
        recargo_map = {21: 5.2, 10: 1.4, 4: 0.5, 0: 0.0}
        if self.chk_recargo.isChecked():
            for pct, rec in recargo_map.items():
                conn.execute("UPDATE tipos_iva SET recargo_porcentaje=? WHERE porcentaje=?", (rec, pct))
        else:
            conn.execute("UPDATE tipos_iva SET recargo_porcentaje=0")
        # Reconfigurar tipos de IVA
        conn.execute("UPDATE tipos_iva SET activo=0")
        orden = 1
        for part in self.inp_iva.text().split(","):
            part = part.strip()
            if not part: continue
            try:
                pct = float(part)
            except ValueError:
                continue
            cur = conn.execute("SELECT id FROM tipos_iva WHERE porcentaje=?", (pct,))
            r = cur.fetchone()
            if r:
                conn.execute("UPDATE tipos_iva SET activo=1, orden=? WHERE id=?", (orden, r["id"]))
            else:
                conn.execute("INSERT INTO tipos_iva (porcentaje, descripcion, activo, orden) VALUES (?,?,1,?)",
                             (pct, f"IVA {pct:g}%", orden))
            orden += 1
        conn.commit()
        conn.close()
        info(self, "Datos de empresa guardados. Todo correcto.")
