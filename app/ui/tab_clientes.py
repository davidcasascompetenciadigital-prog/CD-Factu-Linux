# app/ui/tab_clientes.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QComboBox, QPushButton, QScrollArea, QFrame, QListWidget,
                               QListWidgetItem, QMessageBox, QDialog, QFormLayout, QCheckBox)
from PySide6.QtCore import Qt
from ..db.database import get_connection
from ..models.cliente import Cliente, Contacto
from ..ui.widgets import big_button, title_label, help_popup, info, error, confirm
from ..utils.messages import MSG_CLIENTE_GUARDADO, ayuda
from ..utils.validators import validar_nif_cif, normalizar_dni, normalizar_cif

COMUNIDADES = ["Andalucía","Aragón","Asturias","Baleares","Canarias","Cantabria",
               "Castilla-La Mancha","Castilla y León","Cataluña","Extremadura",
               "Galicia","Madrid","Murcia","Navarra","País Vasco","La Rioja","Ceuta","Melilla"]

class ContactoWidget(QFrame):
    def __init__(self, parent=None, contacto=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        v = QVBoxLayout(self)
        v.setSpacing(6)
        row = QHBoxLayout()
        row.addWidget(QLabel("Nombre:")); self.inp_nom = QLineEdit(contacto.nombre if contacto else "")
        row.addWidget(self.inp_nom)
        row.addWidget(QLabel("Teléfono:")); self.inp_tel = QLineEdit(contacto.telefono if contacto else "")
        row.addWidget(self.inp_tel)
        v.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Email:")); self.inp_email = QLineEdit(contacto.email if contacto else "")
        row.addWidget(self.inp_email)
        row.addWidget(QLabel("Tipo:")); self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItems(["Facturación","Administrativo","Comercial"])
        if contacto: self.cmb_tipo.setCurrentText(contacto.tipo)
        row.addWidget(self.cmb_tipo)
        v.addLayout(row)
        btn_quitar = big_button("Quitar contacto", "secondary")
        btn_quitar.clicked.connect(lambda: self.setParent(None) or self.deleteLater())
        v.addWidget(btn_quitar)

    def to_contacto(self):
        c = Contacto()
        c.nombre = self.inp_nom.text().strip()
        c.telefono = self.inp_tel.text().strip()
        c.email = self.inp_email.text().strip()
        c.tipo = self.cmb_tipo.currentText()
        return c

class ClienteDialog(QDialog):
    def __init__(self, parent=None, cliente_id=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self.setWindowTitle("Ficha de cliente" if cliente_id else "Nuevo cliente")
        self.setMinimumWidth(900)
        outer = QHBoxLayout(self)
        outer.setSpacing(16)

        # ===== Columna izquierda: datos del cliente =====
        left = QVBoxLayout()
        left.setSpacing(8)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)
        self.inp_nombre = QLineEdit()
        self.inp_apell = QLineEdit()
        self.inp_empresa = QLineEdit()
        self.inp_dni = QLineEdit()
        self.inp_dni.textChanged.connect(self._validar_dni)
        self.inp_dni.editingFinished.connect(self._normalizar_dni)
        self.lbl_dni_status = QLabel("")
        self.inp_tel = QLineEdit()
        self.inp_movil = QLineEdit()
        self.inp_email = QLineEdit()
        self.inp_dir = QLineEdit()
        self.inp_cp = QLineEdit()
        self.inp_ciudad = QLineEdit()
        self.cmb_ccaa = QComboBox()
        self.cmb_ccaa.addItems(COMUNIDADES)
        self.inp_pais = QLineEdit("España")
        self.txt_notas = QLineEdit()
        form.addRow("Nombre *:", self.inp_nombre)
        form.addRow("Apellidos:", self.inp_apell)
        form.addRow("Empresa (opcional):", self.inp_empresa)
        dni_row = QHBoxLayout()
        dni_row.addWidget(self.inp_dni)
        dni_row.addWidget(self.lbl_dni_status)
        dni_container = QWidget()
        dni_container.setLayout(dni_row)
        form.addRow("DNI / CIF:", dni_container)
        form.addRow("Teléfono:", self.inp_tel)
        form.addRow("Teléfono móvil:", self.inp_movil)
        form.addRow("Email:", self.inp_email)
        form.addRow("Dirección:", self.inp_dir)
        form.addRow("CP:", self.inp_cp)
        form.addRow("Ciudad:", self.inp_ciudad)
        form.addRow("Comunidad Autónoma:", self.cmb_ccaa)
        form.addRow("País:", self.inp_pais)
        form.addRow("Notas:", self.txt_notas)
        self.chk_recargo = QCheckBox("Activar recargo de equivalencia para este cliente")
        form.addRow("Recargo de equivalencia:", self.chk_recargo)
        left.addLayout(form)
        left.addStretch()

        # ===== Columna derecha: contactos y botones =====
        right = QVBoxLayout()
        right.setSpacing(8)
        self.lbl_deuda = QLabel("Deuda acumulada: 0,00 €")
        self.lbl_deuda.setStyleSheet("font-weight:bold; color:#e53935;")
        right.addWidget(self.lbl_deuda)

        right.addWidget(QLabel("Contactos:"))
        self.contactos_layout = QVBoxLayout()
        right.addLayout(self.contactos_layout)
        btn_add_contacto = big_button("Añadir contacto", "secondary")
        btn_add_contacto.clicked.connect(self.add_contacto)
        right.addWidget(btn_add_contacto)

        right.addStretch()
        row = QHBoxLayout()
        btn_guardar = big_button("GUARDAR", "primary")
        btn_guardar.clicked.connect(self.guardar)
        row.addWidget(btn_guardar)
        btn_cancelar = big_button("Cancelar", "secondary")
        btn_cancelar.clicked.connect(self.reject)
        row.addWidget(btn_cancelar)
        row.addStretch()
        right.addLayout(row)

        outer.addLayout(left, 1)
        outer.addLayout(right, 1)

        if cliente_id is not None:
            self.cargar(cliente_id)

    def _validar_dni(self, texto):
        t = (texto or "").strip()
        if not t:
            self.lbl_dni_status.setText("")
            self.inp_dni.setStyleSheet("")
            return
        from ..utils.validators import validar_nif_cif
        if validar_nif_cif(t):
            self.lbl_dni_status.setText("✓")
            self.lbl_dni_status.setStyleSheet("color:#4caf50; font-weight:bold;")
            self.inp_dni.setStyleSheet("border:2px solid #4caf50;")
        else:
            self.lbl_dni_status.setText("Revisa")
            self.lbl_dni_status.setStyleSheet("color:#e53935; font-weight:bold;")
            self.inp_dni.setStyleSheet("border:2px solid #e53935;")

    def _normalizar_dni(self):
        t = self.inp_dni.text().strip().upper()
        if len(t) == 8 and t.isdigit():
            self.inp_dni.setText(normalizar_dni(t))
        elif len(t) == 8 and t[0].isalpha() and t[1:].isdigit():
            self.inp_dni.setText(normalizar_cif(t))

    def add_contacto(self, contacto=None):
        w = ContactoWidget(self, contacto)
        self.contactos_layout.addWidget(w)

    def cargar(self, cid):
        conn = get_connection()
        r = conn.execute("SELECT * FROM clientes WHERE id=?", (cid,)).fetchone()
        contacts = conn.execute("SELECT * FROM contactos_cliente WHERE cliente_id=?", (cid,)).fetchall()
        conn.close()
        self.inp_nombre.setText(r["nombre"] or "")
        self.inp_apell.setText(r["apellidos"] or "")
        self.inp_empresa.setText(r["empresa"] or "")
        self.inp_dni.setText(r["dni_cif"] or "")
        self.inp_tel.setText(r["telefono"] or "" if "telefono" in r.keys() else "")
        self.inp_movil.setText(r["telefono_movil"] or "" if "telefono_movil" in r.keys() else "")
        self.inp_email.setText(r["email"] or "" if "email" in r.keys() else "")
        self.inp_dir.setText(r["direccion"] or "")
        self.inp_cp.setText(r["cp"] or "")
        self.inp_ciudad.setText(r["ciudad"] or "")
        idx = self.cmb_ccaa.findText(r["comunidad_autonoma"] or "")
        if idx >= 0: self.cmb_ccaa.setCurrentIndex(idx)
        self.inp_pais.setText(r["pais"] or "España")
        self.txt_notas.setText(r["notas"] or "" if "notas" in r.keys() else "")
        self.chk_recargo.setChecked(bool(r["recargo_equivalencia"]) if "recargo_equivalencia" in r.keys() else False)
        # deuda acumulada
        try:
            conn2 = get_connection()
            deuda = conn2.execute("SELECT COALESCE(SUM(pendiente),0) AS d FROM facturas WHERE cliente_id=? AND estado='emitida'", (cid,)).fetchone()["d"]
            conn2.close()
            self.lbl_deuda.setText(f"Deuda acumulada: {deuda:.2f} €")
        except Exception:
            pass
        for c in contacts:
            self.add_contacto(Contacto(id=c["id"], nombre=c["nombre"], telefono=c["telefono"],
                                     email=c["email"], tipo=c["tipo"]))

    def guardar(self):
        if not self.inp_nombre.text().strip():
            error(self, "Falta el nombre del cliente. Escribe aquí: ")
            self.inp_nombre.setFocus()
            return
        conn = get_connection()
        if self.cliente_id is None:
            cur = conn.execute("""INSERT INTO clientes (nombre, apellidos, empresa, dni_cif, telefono, telefono_movil,
                                  email, notas, direccion, cp, ciudad, comunidad_autonoma, pais,
                                  recargo_equivalencia)
                                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                               (self.inp_nombre.text().strip(), self.inp_apell.text().strip(),
                                self.inp_empresa.text().strip() or None,
                                self.inp_dni.text().strip(), self.inp_tel.text().strip(),
                                self.inp_movil.text().strip(), self.inp_email.text().strip(),
                                self.txt_notas.text().strip(), self.inp_dir.text().strip(),
                                self.inp_cp.text().strip(), self.inp_ciudad.text().strip(),
                                self.cmb_ccaa.currentText(), self.inp_pais.text().strip(),
                                1 if self.chk_recargo.isChecked() else 0))
            cliente_id = cur.lastrowid
        else:
            cliente_id = self.cliente_id
            conn.execute("""UPDATE clientes SET nombre=?, apellidos=?, empresa=?, dni_cif=?, telefono=?,
                            telefono_movil=?, email=?, notas=?, direccion=?, cp=?, ciudad=?,
                            comunidad_autonoma=?, pais=?, recargo_equivalencia=?,
                            actualizado_en=datetime('now','localtime')
                            WHERE id=?""",
                         (self.inp_nombre.text().strip(), self.inp_apell.text().strip(),
                          self.inp_empresa.text().strip() or None, self.inp_dni.text().strip(),
                          self.inp_tel.text().strip(), self.inp_movil.text().strip(),
                          self.inp_email.text().strip(), self.txt_notas.text().strip(),
                          self.inp_dir.text().strip(), self.inp_cp.text().strip(),
                          self.inp_ciudad.text().strip(), self.cmb_ccaa.currentText(),
                          self.inp_pais.text().strip(),
                          1 if self.chk_recargo.isChecked() else 0, cliente_id))
            conn.execute("DELETE FROM contactos_cliente WHERE cliente_id=?", (cliente_id,))
        for i in range(self.contactos_layout.count()):
            w = self.contactos_layout.itemAt(i).widget()
            if w is None: continue
            c = w.to_contacto()
            if not c.nombre.strip(): continue
            conn.execute("""INSERT INTO contactos_cliente (cliente_id, nombre, telefono, email, tipo)
                            VALUES (?,?,?,?,?)""",
                         (cliente_id, c.nombre, c.telefono, c.email, c.tipo))
        conn.commit()
        conn.close()
        info(self, MSG_CLIENTE_GUARDADO)
        self.accept()

class TabClientes(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self._all_items = []
        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.addWidget(title_label("Clientes"))

        # Búsqueda
        row = QHBoxLayout()
        row.addWidget(QLabel("Buscar cliente:"))
        self.inp_buscar = QLineEdit()
        self.inp_buscar.setPlaceholderText("Nombre, CIF, dirección, email, teléfono...")
        self.inp_buscar.textChanged.connect(self.filtrar)
        row.addWidget(self.inp_buscar)
        v.addLayout(row)

        # Lista
        self.lista = QListWidget()
        self.lista.setMinimumHeight(260)
        self.lista.itemDoubleClicked.connect(self.editar_item)
        v.addWidget(self.lista)

        # Botones
        row = QHBoxLayout()
        btn_nuevo = big_button("Añadir cliente", "primary")
        btn_nuevo.clicked.connect(self.nuevo_cliente)
        row.addWidget(btn_nuevo)
        btn_editar = big_button("Editar", "secondary")
        btn_editar.clicked.connect(self.editar_seleccionado)
        row.addWidget(btn_editar)
        btn_borrar = big_button("Borrar", "danger")
        btn_borrar.clicked.connect(self.borrar_seleccionado)
        row.addWidget(btn_borrar)
        btn_help = big_button("?", "secondary")
        btn_help.setFixedWidth(60)
        btn_help.clicked.connect(lambda: help_popup(self, ayuda("clientes")))
        row.addWidget(btn_help)
        row.addStretch()
        v.addLayout(row)
        v.addStretch()

        self.refrescar_lista()

    def _texto_item(self, r, contacts):
        parts = [r["nombre"] or "", r["apellidos"] or "", r["empresa"] or "", r["dni_cif"] or "",
                 r["direccion"] or "", r["cp"] or "", r["ciudad"] or "", r["comunidad_autonoma"] or "",
                 r["pais"] or ""]
        for c in contacts:
            parts += [c["nombre"] or "", c["telefono"] or "", c["email"] or ""]
        return " ".join(parts).lower()

    def refrescar_lista(self):
        self.lista.clear()
        self._all_items = []
        conn = get_connection()
        rows = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
        contacts_by_client = {}
        for c in conn.execute("SELECT * FROM contactos_cliente").fetchall():
            contacts_by_client.setdefault(c["cliente_id"], []).append(dict(c))
        conn.close()
        for r in rows:
            rd = dict(r)
            contacts = contacts_by_client.get(rd["id"], [])
            texto = rd["nombre"] + " " + (rd["apellidos"] or "")
            if rd["empresa"]:
                texto += f"  |  Empresa: {rd['empresa']}"
            if rd["dni_cif"]:
                texto += f"  |  {rd['dni_cif']}"
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, rd["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, self._texto_item(rd, contacts))
            self.lista.addItem(item)
            self._all_items.append(item)
        self.filtrar(self.inp_buscar.text())

    def filtrar(self, texto):
        t = (texto or "").strip().lower()
        for item in self._all_items:
            haystack = item.data(Qt.ItemDataRole.UserRole + 1) or ""
            item.setHidden(bool(t) and t not in haystack)

    def nuevo_cliente(self):
        dlg = ClienteDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refrescar_lista()

    def editar_seleccionado(self):
        item = self.lista.currentItem()
        if not item:
            error(self, "Selecciona un cliente de la lista.")
            return
        self.abrir_cliente(item.data(Qt.ItemDataRole.UserRole))

    def borrar_seleccionado(self):
        item = self.lista.currentItem()
        if not item:
            error(self, "Selecciona un cliente de la lista.")
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        conn = get_connection()
        n = conn.execute("SELECT COUNT(*) AS c FROM facturas WHERE cliente_id=?", (cid,)).fetchone()["c"]
        if n > 0:
            conn.close()
            error(self, "No se puede borrar: este cliente figura en facturas emitidas.")
            return
        if not confirm(self, "¿Seguro que quieres borrar este cliente? Se perderán sus datos."):
            conn.close()
            return
        conn.execute("DELETE FROM contactos_cliente WHERE cliente_id=?", (cid,))
        conn.execute("DELETE FROM clientes WHERE id=?", (cid,))
        conn.commit()
        conn.close()
        info(self, "Cliente borrado. Todo correcto.")
        self.refrescar_lista()

    def editar_item(self, item):
        self.abrir_cliente(item.data(Qt.ItemDataRole.UserRole))

    def abrir_cliente(self, cid):
        dlg = ClienteDialog(self, cliente_id=cid)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refrescar_lista()
