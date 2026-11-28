# app/ui/tab_emitir.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QDialog, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt
from datetime import date
import os
from ..db.database import get_connection
from ..models.factura import Factura, LineaFactura
from ..services.hash_chain import hash_registro_factura, qr_payload_url
from ..services.qr_generator import generar_qr_png
from ..services.pdf_generator import generar_pdf_factura
from ..ui.widgets import big_button, title_label, help_popup, info, error, confirm
from ..utils.messages import MSG_FACTURA_GUARDADA, ayuda
from ..config import FACTURAS_DIR

class SelectorClienteDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Elegir cliente")
        self.setMinimumSize(560, 440)
        v = QVBoxLayout(self)
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Buscar por CIF, nombre, dirección, email o teléfono (mín. 4 caracteres)...")
        self.inp.textChanged.connect(self.filtrar)
        v.addWidget(self.inp)
        self.lbl_hint = QLabel("Escribe al menos 4 caracteres para ver sugerencias.")
        v.addWidget(self.lbl_hint)
        self.lista = QListWidget()
        self.lista.itemDoubleClicked.connect(lambda it: self.accept())
        v.addWidget(self.lista)
        btn = big_button("Elegir", "primary")
        btn.clicked.connect(self.accept)
        v.addWidget(btn)
        self.clientes = []
        self.cargar()
    def cargar(self):
        conn = get_connection()
        rows = conn.execute("""SELECT id, nombre, apellidos, empresa, dni_cif, direccion, cp, ciudad,
                               comunidad_autonoma, pais FROM clientes""").fetchall()
        contacts = conn.execute("SELECT cliente_id, telefono, email FROM contactos_cliente").fetchall()
        conn.close()
        contact_map = {}
        for c in contacts:
            contact_map.setdefault(c["cliente_id"], []).append((c["telefono"] or "", c["email"] or ""))
        self.clientes = []
        for r in rows:
            cid = r["id"]
            ct = contact_map.get(cid, [])
            telefonos = " ".join(t for t, e in ct)
            emails = " ".join(e for t, e in ct)
            self.clientes.append({
                "id": cid,
                "nombre": r["nombre"] or "",
                "apellidos": r["apellidos"] or "",
                "empresa": r["empresa"] or "",
                "dni_cif": r["dni_cif"] or "",
                "direccion": r["direccion"] or "",
                "cp": r["cp"] or "",
                "ciudad": r["ciudad"] or "",
                "comunidad": r["comunidad_autonoma"] or "",
                "pais": r["pais"] or "",
                "telefonos": telefonos,
                "emails": emails,
            })
        self.filtrar(self.inp.text())
    def _texto_cliente(self, c):
        partes = [c["nombre"], c["apellidos"], c["empresa"], c["dni_cif"], c["direccion"],
                   c["cp"], c["ciudad"], c["comunidad"], c["pais"], c["telefonos"], c["emails"]]
        return " ".join(p for p in partes if p).lower()
    def filtrar(self, texto):
        self.lista.clear()
        t = (texto or "").strip().lower()
        if not t:
            self.lbl_hint.setText("Listado de clientes. Doble clic para seleccionar.")
        else:
            self.lbl_hint.setText(f"Sugerencias para: {texto.strip()}")
        for c in self.clientes:
            if (not t) or (t in self._texto_cliente(c)):
                nombre = (c["nombre"] + " " + c["apellidos"]).strip()
                if c["empresa"]:
                    nombre += f"  |  Empresa: {c['empresa']}"
                if c["dni_cif"]:
                    nombre += f"  |  CIF: {c['dni_cif']}"
                if c["telefonos"]:
                    nombre += f"  |  Tel: {c['telefonos']}"
                if c["emails"]:
                    nombre += f"  |  Email: {c['emails']}"
                item = QListWidgetItem(nombre)
                item.setData(Qt.ItemDataRole.UserRole, c["id"])
                self.lista.addItem(item)
    def seleccionado_id(self):
        it = self.lista.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

class SelectorProductoDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Elegir producto")
        self.setMinimumSize(500, 400)
        v = QVBoxLayout(self)
        self.lista = QListWidget()
        self.lista.itemDoubleClicked.connect(lambda it: self.accept())
        v.addWidget(self.lista)
        btn = big_button("Añadir", "primary")
        btn.clicked.connect(self.accept)
        v.addWidget(btn)
        conn = get_connection()
        rows = conn.execute("""SELECT p.id, p.nombre, p.importe_base, t.porcentaje, t.id AS iva_id
                               FROM productos p LEFT JOIN tipos_iva t ON t.id=p.tipo_iva_id
                               WHERE p.activo=1 ORDER BY p.nombre""").fetchall()
        conn.close()
        for r in rows:
            item = QListWidgetItem(f"{r['nombre']}  |  {r['importe_base']:.2f} €  |  IVA {r['porcentaje']:g}%")
            item.setData(Qt.ItemDataRole.UserRole, dict(r))
            self.lista.addItem(item)
    def seleccionado(self):
        it = self.lista.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

class TabEmitir(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.cliente_id = None
        self.cliente_data = None
        self.lineas = []
        outer = QHBoxLayout(self)
        outer.setSpacing(16)

        # ===== Columna izquierda: formulario =====
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(title_label("Emitir factura"))

        # 1. Cliente
        left.addWidget(QLabel("1. Cliente:"))
        btn_listado = big_button("Listado de clientes", "primary")
        btn_listado.clicked.connect(self.abrir_listado_clientes)
        left.addWidget(btn_listado)

        # 2. Líneas
        left.addWidget(QLabel("2. Líneas de factura:"))
        row = QHBoxLayout()
        btn_prod = big_button("Añadir producto", "primary")
        btn_prod.clicked.connect(self.add_producto)
        row.addWidget(btn_prod)
        btn_manual = big_button("Escribir línea a mano", "secondary")
        btn_manual.clicked.connect(self.add_manual)
        row.addWidget(btn_manual)
        row.addStretch()
        left.addLayout(row)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(["Concepto", "Cantidad", "Precio", "Dto.%", "IVA", "Total", "Quitar"])
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setMinimumHeight(180)
        self.tabla.verticalHeader().setDefaultSectionSize(32)
        from PySide6.QtWidgets import QSizePolicy
        self.tabla.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left.addWidget(self.tabla)

        # Retención IRPF
        row = QHBoxLayout()
        row.addWidget(QLabel("Retención IRPF (%):"))
        self.inp_irpf = QLineEdit("0")
        self.inp_irpf.setMaximumWidth(80)
        self.inp_irpf.textChanged.connect(lambda t: self.recalcular_resumen())
        row.addWidget(self.inp_irpf)
        row.addWidget(QLabel("(0, 7 o 15 habitualmente)"))
        row.addStretch()
        left.addLayout(row)

        left.addStretch()

        # ===== Columna derecha: resumen automático =====
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(QLabel("3. Resumen automático:"))
        from PySide6.QtWidgets import QFrame
        box = QFrame()
        box.setStyleSheet("background:#1e1e1e; border:1px solid #3a3a3a; border-radius:10px;")
        bv = QVBoxLayout(box)
        bv.setContentsMargins(14, 14, 14, 14)
        self.lbl_base = QLabel("Base imponible total: 0,00 €")
        self.lbl_iva = QLabel("IVA: 0,00 €")
        self.lbl_desglose = QLabel("")
        self.lbl_total = QLabel("Total factura: 0,00 €")
        self.lbl_total.setStyleSheet("font-size:20px; font-weight:bold; color:#4caf50;")
        self.lbl_irpf = QLabel("Retención IRPF: 0,00 €")
        self.lbl_irpf.setStyleSheet("font-size:14px; color:#e53935;")
        self.lbl_irpf.setVisible(False)
        self.lbl_total_pagar = QLabel("Total a pagar: 0,00 €")
        self.lbl_total_pagar.setStyleSheet("font-size:20px; font-weight:bold; color:#4caf50;")
        self.lbl_total_pagar.setVisible(False)
        for l in (self.lbl_base, self.lbl_iva, self.lbl_desglose, self.lbl_total, self.lbl_irpf, self.lbl_total_pagar):
            l.setAlignment(Qt.AlignmentFlag.AlignRight)
            bv.addWidget(l)
        bv.addStretch()
        right.addWidget(box)

        # Datos del cliente seleccionado
        right.addWidget(QLabel("Datos del cliente:"))
        box_cli = QFrame()
        box_cli.setStyleSheet("background:#1e1e1e; border:1px solid #3a3a3a; border-radius:10px;")
        bcv = QVBoxLayout(box_cli)
        bcv.setContentsMargins(14, 14, 14, 14)
        self.lbl_cli_datos = QLabel("Ningún cliente seleccionado")
        self.lbl_cli_datos.setWordWrap(True)
        self.lbl_cli_datos.setStyleSheet("font-size:13px; color:#dddddd;")
        bcv.addWidget(self.lbl_cli_datos)
        bcv.addStretch()
        right.addWidget(box_cli)

        # 4. Estado de cobro
        right.addWidget(QLabel("4. Estado de cobro inicial:"))
        row = QHBoxLayout()
        self.cmb_cobro = QComboBox()
        self.cmb_cobro.addItems(["No cobrada", "Cobrada totalmente", "Cobrada parcialmente"])
        row.addWidget(self.cmb_cobro)
        row.addStretch()
        right.addLayout(row)

        # Campos pago (mini-formulario) visibles si cobrada
        self.pago_frame = QWidget()
        pf = QVBoxLayout(self.pago_frame)
        r = QHBoxLayout()
        r.addWidget(QLabel("Importe a cobrar:")); self.inp_importe_cobro = QLineEdit(); r.addWidget(self.inp_importe_cobro)
        pf.addLayout(r)
        r = QHBoxLayout()
        r.addWidget(QLabel("Forma de pago:")); self.cmb_forma = QComboBox()
        self.cmb_forma.addItems(["Efectivo","Transferencia","Tarjeta","Bizum","Cheque","Otro"]); r.addWidget(self.cmb_forma)
        pf.addLayout(r)
        r = QHBoxLayout()
        r.addWidget(QLabel("Fecha:")); self.inp_fecha_cobro = QLineEdit(date.today().isoformat()); r.addWidget(self.inp_fecha_cobro)
        pf.addLayout(r)
        self.pago_frame.setVisible(False)
        self.cmb_cobro.currentTextChanged.connect(lambda t: self.pago_frame.setVisible(t != "No cobrada"))
        right.addWidget(self.pago_frame)

        # Botones
        row = QHBoxLayout()
        btn_emitir = big_button("Emitir", "primary")
        btn_emitir.clicked.connect(self.emitir)
        row.addWidget(btn_emitir)
        btn_help = big_button("?", "secondary"); btn_help.setFixedWidth(60)
        btn_help.clicked.connect(lambda: help_popup(self, ayuda("emitir")))
        row.addWidget(btn_help)
        row.addStretch()
        right.addLayout(row)

        right.addStretch()

        outer.addLayout(left, 2)
        outer.addLayout(right, 1)

    def abrir_listado_clientes(self):
        dlg = SelectorClienteDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cid = dlg.seleccionado_id()
            if cid is None: return
            self.cliente_id = cid
            conn = get_connection()
            r = conn.execute("SELECT * FROM clientes WHERE id=?", (cid,)).fetchone()
            conn.close()
            self.cliente_data = dict(r)
            # Aviso de recargo de equivalencia por cliente
            re_cli = bool(r["recargo_equivalencia"]) if "recargo_equivalencia" in r.keys() else False
            if re_cli:
                from ..ui.widgets import info
                info(self, "Este cliente tiene activado el recargo de equivalencia. "
                           "Se aplicará automáticamente al emitir la factura.")
            # Datos del cliente en el recuadro derecho
            conn2 = get_connection()
            contacts = conn2.execute("SELECT telefono, email FROM contactos_cliente WHERE cliente_id=?", (cid,)).fetchall()
            conn2.close()
            tels = ", ".join(c["telefono"] for c in contacts if c["telefono"])
            emails = ", ".join(c["email"] for c in contacts if c["email"])
            datos = (f"Nombre: {r['nombre']} {r['apellidos'] or ''}\n"
                     f"Empresa: {r['empresa'] or '-'}\n"
                     f"NIF/CIF: {r['dni_cif'] or '-'}\n"
                     f"Dirección: {r['direccion'] or '-'}\n"
                     f"CP/Ciudad: {r['cp'] or ''} {r['ciudad'] or ''}\n"
                     f"Teléfono: {tels or '-'}\n"
                     f"Email: {emails or '-'}")
            self.lbl_cli_datos.setText(datos)


    def add_producto(self):
        dlg = SelectorProductoDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.seleccionado()
            if not data: return
            linea = LineaFactura(concepto=data["nombre"] if "nombre" in data else data.get("nombre",""),
                                cantidad=1.0, importe_base=float(data["importe_base"]),
                                porcentaje_iva=float(data["porcentaje"]), producto_id=data["id"],
                                tipo_iva_id=data["iva_id"])
            # fetch nombre properly
            conn = get_connection()
            r = conn.execute("SELECT nombre FROM productos WHERE id=?", (data["id"],)).fetchone()
            tr = conn.execute("SELECT porcentaje FROM tipos_iva WHERE id=?", (data["iva_id"],)).fetchone()
            conn.close()
            linea.concepto = r["nombre"]
            pct_iva = tr["porcentaje"] if tr else linea.porcentaje_iva
            linea.porcentaje_recargo = self._recargo_pct_para_iva(pct_iva)
            linea.recalcular()
            self.lineas.append(linea)
            self.refrescar_tabla()
            self.recalcular_resumen()

    def add_manual(self):
        # mini dialog inline: ask concepto, base, iva
        from PySide6.QtWidgets import QInputDialog
        concepto, ok = QInputDialog.getText(self, "Línea manual", "Concepto:")
        if not ok or not concepto.strip(): return
        base_str, ok = QInputDialog.getText(self, "Línea manual", "Importe base (sin IVA):")
        if not ok: return
        try:
            base = float(base_str.replace(",", "."))
        except ValueError:
            error(self, "El importe base debe ser un número.")
            return
        # IVA selector
        dlg = QDialog(self)
        dlg.setWindowTitle("IVA")
        v = QVBoxLayout(dlg)
        cmb = QComboBox()
        conn = get_connection()
        for r in conn.execute("SELECT id, porcentaje FROM tipos_iva WHERE activo=1 ORDER BY orden"):
            cmb.addItem(f"{r['porcentaje']:g}%", r["id"])
        conn.close()
        v.addWidget(QLabel("IVA que se aplica:"))
        v.addWidget(cmb)
        btn = big_button("Aceptar", "primary")
        btn.clicked.connect(dlg.accept)
        v.addWidget(btn)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        iva_id = cmb.currentData()
        conn = get_connection()
        r = conn.execute("SELECT porcentaje, recargo_porcentaje FROM tipos_iva WHERE id=?", (iva_id,)).fetchone()
        conn.close()
        pct = r["porcentaje"] if r else 21.0
        rec = self._recargo_pct_para_iva(pct)
        linea = LineaFactura(concepto=concepto.strip(), cantidad=1.0, importe_base=base,
                            porcentaje_iva=pct, porcentaje_recargo=rec, tipo_iva_id=iva_id)
        linea.recalcular()
        self.lineas.append(linea)
        self.refrescar_tabla()
        self.recalcular_resumen()

    def refrescar_tabla(self):
        self.tabla.setRowCount(0)
        for i, l in enumerate(self.lineas):
            self.tabla.insertRow(i)
            self.tabla.setItem(i, 0, QTableWidgetItem(l.concepto))
            # Cantidad (editable)
            from PySide6.QtWidgets import QLineEdit
            inp_cant = QLineEdit(f"{l.cantidad:g}")
            inp_cant.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inp_cant.textChanged.connect(lambda t, idx=i: self._cambiar_cantidad(idx, t))
            self.tabla.setCellWidget(i, 1, inp_cant)
            it_precio = QTableWidgetItem(f"{l.importe_base:.2f} €")
            it_precio.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(i, 2, it_precio)
            # Descuento % (editable)
            inp_desc = QLineEdit(f"{l.descuento:g}")
            inp_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inp_desc.textChanged.connect(lambda t, idx=i: self._cambiar_descuento(idx, t))
            self.tabla.setCellWidget(i, 3, inp_desc)
            it_iva = QTableWidgetItem(f"{l.porcentaje_iva:g}%")
            it_iva.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(i, 4, it_iva)
            it_total = QTableWidgetItem(f"{l.total_linea:.2f} €")
            it_total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(i, 5, it_total)
            btn = big_button("Quitar", "danger")
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda checked, idx=i: self.quitar_linea(idx))
            self.tabla.setCellWidget(i, 6, btn)
        self.tabla.setMinimumHeight(max(180, self.tabla.rowCount() * 34 + 40))

    def _cambiar_cantidad(self, idx, texto):
        if idx < 0 or idx >= len(self.lineas):
            return
        try:
            c = float((texto or "1").replace(",", "."))
            if c <= 0:
                c = 1.0
        except ValueError:
            c = 1.0
        self.lineas[idx].cantidad = c
        self.lineas[idx].recalcular()
        self.refrescar_tabla()
        self.recalcular_resumen()

    def _cambiar_descuento(self, idx, texto):
        if idx < 0 or idx >= len(self.lineas):
            return
        try:
            d = float((texto or "0").replace(",", "."))
        except ValueError:
            d = 0.0
        self.lineas[idx].descuento = d
        self.lineas[idx].recalcular()
        self.refrescar_tabla()
        self.recalcular_resumen()

    def quitar_linea(self, idx):
        if not confirm(self, "¿Seguro que quieres quitar esta línea?"):
            return
        if 0 <= idx < len(self.lineas):
            self.lineas.pop(idx)
            self.refrescar_tabla()
            self.recalcular_resumen()

    def recalcular_resumen(self):
        f = Factura(lineas=self.lineas)
        # Recargo de equivalencia
        for l in f.lineas:
            l.porcentaje_recargo = self._recargo_pct_para_iva(l.porcentaje_iva)
        try:
            f.irpf_porcentaje = float((self.inp_irpf.text() or "0").replace(",", "."))
        except ValueError:
            f.irpf_porcentaje = 0.0
        f.recalcular_totales()
        self.lbl_base.setText(f"Base imponible total: {f.base_imponible:.2f} €")
        self.lbl_iva.setText(f"IVA total: {f.total_iva:.2f} €")
        desglose_txt = "  |  ".join(f"IVA {pct:g}%: {cuota:.2f} €" for pct, (b, cuota) in f.desglose_iva.items())
        self.lbl_desglose.setText(desglose_txt)
        self.lbl_total.setText(f"Total factura: {f.total_factura:.2f} €")
        if f.irpf_porcentaje and f.irpf_porcentaje > 0:
            self.lbl_irpf.setText(f"Retención IRPF ({f.irpf_porcentaje:g}%): -{f.irpf_importe:.2f} €")
            self.lbl_total_pagar.setText(f"Total a pagar: {f.total_a_pagar:.2f} €")
            self.lbl_irpf.setVisible(True)
            self.lbl_total_pagar.setVisible(True)
        else:
            self.lbl_irpf.setVisible(False)
            self.lbl_total_pagar.setVisible(False)
        self._totales_cache = f

    def _recargo_activo(self):
        # Recargo si está activo en empresa o en el cliente seleccionado
        try:
            conn = get_connection()
            r = conn.execute("SELECT recargo_equivalencia_enabled FROM empresa WHERE id=1").fetchone()
            conn.close()
            emp_re = bool(r["recargo_equivalencia_enabled"]) if r and "recargo_equivalencia_enabled" in r.keys() else False
        except Exception:
            emp_re = False
        cli_re = False
        if self.cliente_data:
            cli_re = bool(self.cliente_data.get("recargo_equivalencia"))
        return emp_re or cli_re

    def _recargo_pct_para_iva(self, pct):
        if not self._recargo_activo():
            return 0.0
        mapa = {21: 5.2, 10: 1.4, 4: 0.5, 0: 0.0}
        # buscar el más cercano
        for k, v in mapa.items():
            if abs(k - pct) < 0.01:
                return v
        return 0.0

    def emitir(self):
        if self.cliente_id is None:
            error(self, "Falta elegir un cliente. Pulsa 'Elegir cliente'.")
            return
        if not self.lineas:
            error(self, "Añade al menos una línea de factura.")
            return
        f = Factura(lineas=[LineaFactura(**{k: getattr(l, k) for k in l.__dataclass_fields__}) for l in self.lineas])
        # rebuild cleanly
        f.lineas = []
        for l in self.lineas:
            nl = LineaFactura(concepto=l.concepto, cantidad=l.cantidad, importe_base=l.importe_base,
                              porcentaje_iva=l.porcentaje_iva, descuento=l.descuento,
                              producto_id=l.producto_id, tipo_iva_id=l.tipo_iva_id)
            nl.recalcular()
            f.lineas.append(nl)
        # Recargo de equivalencia
        for l in f.lineas:
            l.porcentaje_recargo = self._recargo_pct_para_iva(l.porcentaje_iva)
        try:
            f.irpf_porcentaje = float((self.inp_irpf.text() or "0").replace(",", "."))
        except ValueError:
            f.irpf_porcentaje = 0.0
        f.recalcular_totales()
        # cliente nombre para confirmación
        nombre_cliente = self.cliente_data.get("empresa") or f"{self.cliente_data['nombre']} {self.cliente_data.get('apellidos') or ''}".strip()
        if not confirm(self, f"Vas a emitir una factura a {nombre_cliente} por {f.total_factura:.2f} €. ¿Es correcto?"):
            return
        # número de factura
        conn = get_connection()
        año = date.today().year
        cur = conn.execute("SELECT COUNT(*) AS c FROM facturas WHERE strftime('%Y', fecha_emision)=?", (str(año),))
        seq = (cur.fetchone()["c"] or 0) + 1
        numero = f"{año}-{seq:06d}"
        # hash anterior
        last = conn.execute("SELECT hash_registro FROM registros_facturacion ORDER BY id DESC LIMIT 1").fetchone()
        hash_anterior = last["hash_registro"] if last else None
        nif_receptor = self.cliente_data.get("dni_cif") or ""
        # nif emisor
        emp = conn.execute("SELECT nif, verifactu_enabled FROM empresa WHERE id=1").fetchone()
        nif_emisor = (emp["nif"] if emp else "") or ""
        verificable = bool(emp["verifactu_enabled"]) if emp and "verifactu_enabled" in emp.keys() else False
        hash_reg = hash_registro_factura(numero, date.today().isoformat(), nif_emisor, nif_receptor,
                                        f.base_imponible, f.total_factura, hash_anterior)
        qr_payload = qr_payload_url(numero, nif_emisor, date.today().isoformat(), f.total_factura, verificable)

        # insert factura
        cur = conn.execute("""INSERT INTO facturas (numero, fecha_emision, cliente_id, base_imponible, total_iva,
                              total_factura, estado, estado_cobro, pendiente, hash_registro, hash_anterior,
                              irpf_porcentaje, irpf_importe, total_a_pagar, recargo_importe)
                              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (numero, date.today().isoformat(), self.cliente_id, f.base_imponible,
                            f.total_iva, f.total_factura, "emitida", "no_cobrada", f.total_factura,
                            hash_reg, hash_anterior, f.irpf_porcentaje, f.irpf_importe, f.total_a_pagar,
                            f.recargo_importe))
        factura_id = cur.lastrowid
        # lineas
        for i, l in enumerate(f.lineas):
            conn.execute("""INSERT INTO lineas_factura (factura_id, orden, producto_id, concepto, cantidad,
                            importe_base, tipo_iva_id, porcentaje_iva, porcentaje_recargo, base_linea, iva_linea,
                            recargo_linea, total_linea)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (factura_id, i, l.producto_id, l.concepto, l.cantidad, l.importe_base,
                          l.tipo_iva_id, l.porcentaje_iva, l.porcentaje_recargo, l.base_linea, l.iva_linea,
                          l.recargo_linea, l.total_linea))
        # desglose
        for pct, (base, cuota) in f.desglose_iva.items():
            # tipo_iva_id lookup
            t = conn.execute("SELECT id FROM tipos_iva WHERE porcentaje=?", (pct,)).fetchone()
            tid = t["id"] if t else None
            conn.execute("""INSERT INTO desglose_iva_factura (factura_id, tipo_iva_id, porcentaje, base, cuota)
                            VALUES (?,?,?,?,?)""", (factura_id, tid, pct, base, cuota))
        # registro facturacion
        conn.execute("""INSERT INTO registros_facturacion (factura_id, tipo, numero_factura, fecha_emision,
                        nif_emisor, nif_receptor, base_imponible, total_factura, hash_registro,
                        hash_anterior, qr_payload)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (factura_id, "alta", numero, date.today().isoformat(), nif_emisor, nif_receptor,
                      f.base_imponible, f.total_factura, hash_reg, hash_anterior, qr_payload))
        conn.commit()

        # QR
        qr_path = FACTURAS_DIR / str(año) / f"{numero}.png"
        qr_path.parent.mkdir(parents=True, exist_ok=True)
        generar_qr_png(qr_payload, qr_path)

        # PDF
        pdf_path = FACTURAS_DIR / str(año) / f"{numero}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        # build cliente-like object
        class C: pass
        c = C()
        c.nombre = self.cliente_data["nombre"]; c.apellidos = self.cliente_data.get("apellidos")
        c.empresa = self.cliente_data.get("empresa"); c.dni_cif = self.cliente_data.get("dni_cif")
        c.direccion = self.cliente_data.get("direccion"); c.cp = self.cliente_data.get("cp")
        c.ciudad = self.cliente_data.get("ciudad")
        def _nombre_mostrar():
            if c.empresa: return f"Empresa: {c.empresa}"
            return f"{c.nombre} {c.apellidos or ''}".strip()
        c.nombre_mostrar = _nombre_mostrar
        # empresa
        er = conn.execute("SELECT * FROM empresa WHERE id=1").fetchone()
        class E: pass
        e = E()
        e.nombre = er["nombre"]; e.nif = er["nif"]; e.direccion = er["direccion"]
        e.cp = er["cp"]; e.ciudad = er["ciudad"]; e.comunidad_autonoma = er["comunidad_autonoma"]
        e.pais = er["pais"]; e.logo_path = er["logo_path"]
        e.registro_mercantil = er["registro_mercantil"] if "registro_mercantil" in er.keys() else None
        f.numero = numero
        f.fecha_emision = date.today().isoformat()

        # estado cobro inicial
        estado_cobro = "no_cobrada"
        pendiente = f.total_factura
        cobros_list = []
        estado_txt = self.cmb_cobro.currentText()
        if estado_txt == "Cobrada totalmente":
            imp = f.total_factura
            fecha_cobro = date.today().isoformat()
            conn.execute("""INSERT INTO cobros (factura_id, fecha_cobro, importe, forma_pago) VALUES (?,?,?,?)""",
                         (factura_id, fecha_cobro, imp, self.cmb_forma.currentText()))
            estado_cobro = "pagada"
            pendiente = 0.0
            cobros_list.append({"fecha": fecha_cobro, "importe": imp, "forma_pago": self.cmb_forma.currentText()})
            conn.execute("UPDATE facturas SET estado_cobro='pagada', pendiente=0 WHERE id=?", (factura_id,))
        elif estado_txt == "Cobrada parcialmente":
            try:
                imp = float(self.inp_importe_cobro.text().replace(",", "."))
            except ValueError:
                imp = f.total_factura
            fecha_cobro = self.inp_fecha_cobro.text() or date.today().isoformat()
            conn.execute("""INSERT INTO cobros (factura_id, fecha_cobro, importe, forma_pago) VALUES (?,?,?,?)""",
                         (factura_id, fecha_cobro, imp, self.cmb_forma.currentText()))
            pend = round(f.total_factura - imp, 2)
            nuevo_estado = "pagada" if pend <= 0 else "parcial"
            estado_cobro = nuevo_estado
            pendiente = max(pend, 0)
            cobros_list.append({"fecha": fecha_cobro, "importe": imp, "forma_pago": self.cmb_forma.currentText()})
            conn.execute("UPDATE facturas SET estado_cobro=?, pendiente=? WHERE id=?",
                         (nuevo_estado, max(pend, 0), factura_id))
        conn.commit()

        # datos de cobro para el PDF
        f.estado_cobro = estado_cobro
        f.pendiente = pendiente
        f.cobros = cobros_list

        generar_pdf_factura(f, e, c, f.lineas, f.desglose_iva, str(qr_path), str(pdf_path))
        conn.execute("UPDATE facturas SET pdf_path=? WHERE id=?", (str(pdf_path), factura_id))
        conn.commit()
        conn.close()

        # abrir PDF
        try:
            os.startfile(str(pdf_path))
        except Exception:
            pass

        info(self, MSG_FACTURA_GUARDADA)
        # reset
        self.lineas = []
        self.cliente_id = None
        self.cliente_data = None
        self.lbl_cli_datos.setText("Ningún cliente seleccionado")
        self.refrescar_tabla()
        self.recalcular_resumen()
        self.cmb_cobro.setCurrentText("No cobrada")
        self.pago_frame.setVisible(False)
        self.inp_irpf.setText("0")
        # refrescar otras pestañas
        try:
            self.parent.tab_facturas.refrescar()
            self.parent.tab_cobros.refrescar()
        except Exception:
            pass
