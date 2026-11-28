# app/ui/tab_facturas.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                               QAbstractItemView, QFileDialog, QDialog, QScrollArea, QFrame)
from PySide6.QtCore import Qt
import os
import os
from ..db.database import get_connection
from ..models.factura import Factura, LineaFactura
from ..services.hash_chain import qr_payload_url
from ..services.qr_generator import generar_qr_png
from ..services.pdf_generator import generar_pdf_factura, generar_pdf_facturas
from ..config import FACTURAS_DIR, resource_path
from ..ui.widgets import big_button, title_label, help_popup, info, error, confirm
from ..utils.messages import ayuda
from ..services.verifactu_export import exportar_csv
from ..config import FACTURAS_DIR

class VisorFacturaDialog(QDialog):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle(f"Factura {data['factura'].numero}")
        self.setMinimumSize(700, 600)
        v = QVBoxLayout(self)
        f = data["factura"]; e = data["empresa"]; c = data["cliente"]

        v.addWidget(QLabel(f"<b>FACTURA Nº {f.numero}</b>"))
        v.addWidget(QLabel(f"Fecha: {f.fecha_emision}"))

        # Dos columnas: emisor (izq) y cliente (der)
        cols = QHBoxLayout()
        # Emisor
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Emisor:</b>"))
        left.addWidget(QLabel(f"<b>{e.nombre}</b>"))
        left.addWidget(QLabel(f"NIF: {e.nif}"))
        left.addWidget(QLabel(f"{e.direccion}, {e.cp} {e.ciudad}"))
        left.addWidget(QLabel(f"{e.comunidad_autonoma}, {e.pais}"))
        if getattr(e, "registro_mercantil", None):
            left.addWidget(QLabel(f"Reg. Mercantil: {e.registro_mercantil}"))
        left.addStretch()
        # Cliente
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Cliente:</b>"))
        right.addWidget(QLabel(c.nombre_mostrar()))
        dni = c.dni_cif if hasattr(c, "dni_cif") else ""
        right.addWidget(QLabel(f"NIF/CIF: {dni}"))
        right.addWidget(QLabel(f"{c.direccion}, {c.cp} {c.ciudad}"))
        right.addStretch()
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        v.addLayout(cols)

        # Líneas
        v.addWidget(QLabel("<b>Líneas:</b>"))
        tabla = QTableWidget(0, 6)
        tabla.setHorizontalHeaderLabels(["Concepto", "Cant.", "Precio", "Dto.%", "IVA %", "Total"])
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        total_desc = 0.0
        for i, l in enumerate(data["lineas"]):
            tabla.insertRow(i)
            tabla.setItem(i, 0, QTableWidgetItem(l.concepto))
            it = QTableWidgetItem(f"{l.cantidad:g}"); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); tabla.setItem(i, 1, it)
            it = QTableWidgetItem(f"{l.importe_base:.2f} €"); it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); tabla.setItem(i, 2, it)
            desc = getattr(l, "descuento", 0.0) or 0.0
            total_desc += l.cantidad * l.importe_base * desc / 100.0
            it = QTableWidgetItem(f"{desc:g}%"); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); tabla.setItem(i, 3, it)
            it = QTableWidgetItem(f"{l.porcentaje_iva:.0f}%"); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); tabla.setItem(i, 4, it)
            it = QTableWidgetItem(f"{l.total_linea:.2f} €"); it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); tabla.setItem(i, 5, it)
        tabla.setMinimumHeight(120)
        v.addWidget(tabla)

        # Desglose
        v.addWidget(QLabel("<b>Desglose de IVA:</b>"))
        for pct, (base, cuota) in data["desglose"].items():
            v.addWidget(QLabel(f"IVA {pct:.0f}%: base {base:.2f} € + cuota {cuota:.2f} €"))

        v.addWidget(QLabel(f"<b>Base imponible total: {f.base_imponible:.2f} €</b>"))
        v.addWidget(QLabel(f"<b>Total descuento: {total_desc:.2f} €</b>"))
        v.addWidget(QLabel(f"<b>Total factura: {f.total_factura:.2f} €</b>"))
        rec_imp = getattr(f, "recargo_importe", 0.0) or 0.0
        if rec_imp and rec_imp > 0:
            v.addWidget(QLabel(f"Recargo de equivalencia: {rec_imp:.2f} €"))
        irpf_pct = getattr(f, "irpf_porcentaje", 0.0) or 0.0
        irpf_imp = getattr(f, "irpf_importe", 0.0) or 0.0
        if irpf_pct and irpf_pct > 0:
            v.addWidget(QLabel(f"Retención IRPF ({irpf_pct:g}%): -{irpf_imp:.2f} €"))
            tp = getattr(f, "total_a_pagar", None)
            if tp is None:
                tp = f.total_factura - irpf_imp
            v.addWidget(QLabel(f"<b>Total a pagar: {tp:.2f} €</b>"))

        # Cobros
        v.addWidget(QLabel("<b>Cobros:</b>"))
        estado = getattr(f, "estado_cobro", "no_cobrada") or "no_cobrada"
        etiqueta = {"pagada": "Pagada", "parcial": "Parcial", "no_cobrada": "Pendiente"}.get(estado, estado)
        v.addWidget(QLabel(f"Estado de cobro: {etiqueta}"))
        v.addWidget(QLabel(f"Pendiente: {getattr(f, 'pendiente', 0.0):.2f} €"))
        cobros = getattr(f, "cobros", None) or []
        if cobros:
            for c in cobros:
                v.addWidget(QLabel(f"  - {c.get('fecha','')}: {float(c.get('importe',0)):.2f} € ({c.get('forma_pago','')})"))
        else:
            v.addWidget(QLabel("Sin cobros registrados."))

        # Botones
        row = QHBoxLayout()
        btn_imp = big_button("Imprimir", "primary")
        btn_imp.clicked.connect(self.imprimir)
        row.addWidget(btn_imp)
        btn_cerrar = big_button("Cerrar", "secondary")
        btn_cerrar.clicked.connect(self.accept)
        row.addWidget(btn_cerrar)
        row.addStretch()
        v.addLayout(row)

    def imprimir(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", f"{self.data['factura'].numero}.pdf", "PDF (*.pdf)")
        if not path:
            return
        generar_pdf_factura(self.data["factura"], self.data["empresa"], self.data["cliente"],
                          self.data["lineas"], self.data["desglose"], self.data["qr_path"], path)
        info(self, "PDF generado. Todo correcto.")
        try:
            os.startfile(path)
        except Exception:
            pass

class TabFacturas(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.addWidget(title_label("Facturas emitidas"))

        self.tabla = QTableWidget(0, 9)
        self.tabla.setHorizontalHeaderLabels(["Sel", "Núm.FRA.", "Fecha", "Nombre", "DNI/CIF", "Base", "IVA", "Total", "Estado"])
        # Fecha: tamaño justo; Nombre: mayor; resto ajusta a su dato
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tabla.setMinimumHeight(320)
        self.tabla.itemDoubleClicked.connect(self.ver_factura)
        self.tabla.setColumnWidth(0, 30)
        self.tabla.setColumnWidth(2, 90)
        v.addWidget(self.tabla)

        row = QHBoxLayout()
        btn_ver = big_button("Ver factura", "primary")
        btn_ver.clicked.connect(self.ver_factura)
        row.addWidget(btn_ver)
        btn_imp = big_button("Imprimir PDF", "primary")
        btn_imp.clicked.connect(self.imprimir_seleccionadas)
        row.addWidget(btn_imp)
        btn_cobro = big_button("Registrar cobro", "primary")
        btn_cobro.clicked.connect(self.registrar_cobro)
        row.addWidget(btn_cobro)
        btn_anular = big_button("Anular / Rectificar", "danger")
        btn_anular.clicked.connect(self.anular)
        row.addWidget(btn_anular)
        btn_export = big_button("Exportar asesor", "secondary")
        btn_export.clicked.connect(self.exportar)
        row.addWidget(btn_export)
        btn_help = big_button("?", "secondary"); btn_help.setFixedWidth(60)
        btn_help.clicked.connect(lambda: help_popup(self, ayuda("facturas")))
        row.addWidget(btn_help)
        row.addStretch()
        v.addLayout(row)
        v.addStretch()

        self.refrescar()

    def refrescar(self):
        self.tabla.setRowCount(0)
        conn = get_connection()
        rows = conn.execute("""
            SELECT f.id, f.fecha_emision, f.numero, f.base_imponible, f.total_iva, f.total_factura,
                   f.estado, f.estado_cobro, f.pdf_path, c.nombre, c.apellidos, c.empresa, c.dni_cif
            FROM facturas f JOIN clientes c ON c.id=f.cliente_id
            ORDER BY f.fecha_emision DESC, f.id DESC
        """).fetchall()
        conn.close()
        for i, r in enumerate(rows):
            self.tabla.insertRow(i)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            chk.setData(Qt.ItemDataRole.UserRole, (r["id"], r["pdf_path"]))
            self.tabla.setItem(i, 0, chk)
            # Núm.FRA.
            it_num = QTableWidgetItem(r["numero"] or "")
            it_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(i, 1, it_num)
            # Fecha formato es_ES
            try:
                from datetime import datetime
                fecha_es = datetime.strptime(r["fecha_emision"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                fecha_es = r["fecha_emision"]
            it_fecha = QTableWidgetItem(fecha_es)
            it_fecha.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(i, 2, it_fecha)
            nombre = r["empresa"] if r["empresa"] else f"{r['nombre']} {r['apellidos'] or ''}".strip()
            self.tabla.setItem(i, 3, QTableWidgetItem(nombre))
            self.tabla.setItem(i, 4, QTableWidgetItem(r["dni_cif"] or ""))
            it_base = QTableWidgetItem(f"{r['base_imponible']:.2f} €")
            it_base.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(i, 5, it_base)
            it_iva = QTableWidgetItem(f"{r['total_iva']:.2f} €")
            it_iva.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(i, 6, it_iva)
            it_total = QTableWidgetItem(f"{r['total_factura']:.2f} €")
            it_total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(i, 7, it_total)
            estado = r["estado_cobro"]
            if r["estado"] == "anulada":
                estado = "Anulada"
            elif estado == "pagada":
                estado = "Pagada"
            elif estado == "parcial":
                estado = "Parcial"
            else:
                estado = "Pendiente"
            self.tabla.setItem(i, 8, QTableWidgetItem(estado))

    def _fila_seleccionada(self):
        row = self.tabla.currentRow()
        if row < 0:
            error(self, "Selecciona una factura de la lista.")
            return None
        item = self.tabla.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _cargar_datos_factura(self, fid):
        conn = get_connection()
        fr = conn.execute("SELECT * FROM facturas WHERE id=?", (fid,)).fetchone()
        if not fr:
            conn.close()
            return None
        cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (fr["cliente_id"],)).fetchone()
        lineas = conn.execute("SELECT * FROM lineas_factura WHERE factura_id=? ORDER BY orden", (fid,)).fetchall()
        desglose = conn.execute("SELECT * FROM desglose_iva_factura WHERE factura_id=?", (fid,)).fetchall()
        cobros = conn.execute("SELECT fecha_cobro, importe, forma_pago FROM cobros WHERE factura_id=? ORDER BY id", (fid,)).fetchall()
        reg = conn.execute("SELECT qr_payload FROM registros_facturacion WHERE factura_id=? LIMIT 1", (fid,)).fetchone()
        emp = conn.execute("SELECT * FROM empresa WHERE id=1").fetchone()
        conn.close()

        f = Factura()
        f.id = fr["id"]; f.numero = fr["numero"]; f.fecha_emision = fr["fecha_emision"]
        f.base_imponible = fr["base_imponible"]; f.total_iva = fr["total_iva"]
        f.total_factura = fr["total_factura"]
        f.lineas = []
        for l in lineas:
            nl = LineaFactura(concepto=l["concepto"], cantidad=l["cantidad"], importe_base=l["importe_base"],
                              porcentaje_iva=l["porcentaje_iva"],
                              porcentaje_recargo=(l["porcentaje_recargo"] if "porcentaje_recargo" in l.keys() else 0.0),
                              producto_id=l["producto_id"], tipo_iva_id=l["tipo_iva_id"])
            nl.base_linea = l["base_linea"]; nl.iva_linea = l["iva_linea"]
            nl.recargo_linea = (l["recargo_linea"] if "recargo_linea" in l.keys() else 0.0)
            nl.total_linea = l["total_linea"]
            f.lineas.append(nl)
        f.desglose_iva = {d["porcentaje"]: (d["base"], d["cuota"]) for d in desglose}
        f.estado_cobro = fr["estado_cobro"]
        f.pendiente = fr["pendiente"]
        f.irpf_porcentaje = fr["irpf_porcentaje"] if "irpf_porcentaje" in fr.keys() else 0.0
        f.irpf_importe = fr["irpf_importe"] if "irpf_importe" in fr.keys() else 0.0
        f.recargo_importe = fr["recargo_importe"] if "recargo_importe" in fr.keys() else 0.0
        f.total_a_pagar = fr["total_a_pagar"] if "total_a_pagar" in fr.keys() else f.total_factura - f.irpf_importe
        f.cobros = [{"fecha": c["fecha_cobro"], "importe": c["importe"], "forma_pago": c["forma_pago"]} for c in cobros]

        class C: pass
        c = C()
        c.nombre = cliente["nombre"]; c.apellidos = cliente["apellidos"]; c.empresa = cliente["empresa"]
        c.dni_cif = cliente["dni_cif"]; c.direccion = cliente["direccion"]; c.cp = cliente["cp"]
        c.ciudad = cliente["ciudad"]
        def nm():
            if c.empresa: return f"Empresa: {c.empresa}"
            return f"{c.nombre} {c.apellidos or ''}".strip()
        c.nombre_mostrar = nm

        class E: pass
        e = E()
        e.nombre = emp["nombre"]; e.nif = emp["nif"]; e.direccion = emp["direccion"]
        e.cp = emp["cp"]; e.ciudad = emp["ciudad"]; e.comunidad_autonoma = emp["comunidad_autonoma"]
        e.pais = emp["pais"]; e.logo_path = emp["logo_path"]
        e.registro_mercantil = emp["registro_mercantil"] if "registro_mercantil" in emp.keys() else None

        qr_path = FACTURAS_DIR / fr["fecha_emision"][:4] / f"{fr['numero']}.png"
        qr_path.parent.mkdir(parents=True, exist_ok=True)
        if reg:
            generar_qr_png(reg["qr_payload"], qr_path)
        return {"factura": f, "empresa": e, "cliente": c, "lineas": f.lineas,
                "desglose": f.desglose_iva, "qr_path": str(qr_path)}

    def imprimir_factura_doble(self, item):
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not data:
            row = item.row() if hasattr(item, "row") else self.tabla.row(item)
            first = self.tabla.item(row, 0)
            data = first.data(Qt.ItemDataRole.UserRole) if first else None
        if not data:
            return
        fid, _ = data
        d = self._cargar_datos_factura(fid)
        if not d:
            error(self, "No se encontró la factura.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", f"{d['factura'].numero}.pdf", "PDF (*.pdf)")
        if not path:
            return
        generar_pdf_factura(d["factura"], d["empresa"], d["cliente"], d["lineas"], d["desglose"], d["qr_path"], path)
        info(self, "PDF generado. Todo correcto.")
        try:
            os.startfile(path)
        except Exception:
            pass

    def ver_factura(self, item=None):
        data = None
        if item is not None:
            d = item.data(Qt.ItemDataRole.UserRole) if hasattr(item, "data") else None
            if d:
                fid, _ = d
                data = self._cargar_datos_factura(fid)
        if data is None:
            sel = self._fila_seleccionada()
            if not sel:
                return
            fid, _ = sel
            data = self._cargar_datos_factura(fid)
        if not data:
            error(self, "No se encontró la factura.")
            return
        dlg = VisorFacturaDialog(self, data)
        dlg.exec()

    def imprimir_seleccionadas(self):
        lista = []
        for row in range(self.tabla.rowCount()):
            chk = self.tabla.item(row, 0)
            if chk is not None and chk.checkState() == Qt.CheckState.Checked:
                data = chk.data(Qt.ItemDataRole.UserRole)
                if not data:
                    continue
                fid, _ = data
                d = self._cargar_datos_factura(fid)
                if d:
                    lista.append(d)
        if not lista:
            error(self, "Marca con el recuadro una o varias facturas de la lista.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", "facturas_seleccionadas.pdf", "PDF (*.pdf)")
        if not path:
            return
        generar_pdf_facturas(lista, path)
        info(self, f"PDF con {len(lista)} factura(s) generado. Todo correcto.")
        try:
            os.startfile(path)
        except Exception:
            pass

    def ver_pdf(self):
        data = self._fila_seleccionada()
        if not data: return
        fid, pdf_path = data
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.startfile(pdf_path)
            except Exception:
                error(self, "No se pudo abrir el PDF.")
        else:
            error(self, "No se encontró el PDF de esta factura.")

    def registrar_cobro(self):
        data = self._fila_seleccionada()
        if not data: return
        # delegar en pestaña cobros seleccionando
        fid, _ = data
        try:
            self.parent.tab_cobros.seleccionar(fid, None)
            # need pendiente; fetch
            conn = get_connection()
            r = conn.execute("SELECT pendiente FROM facturas WHERE id=?", (fid,)).fetchone()
            conn.close()
            self.parent.tab_cobros.inp_importe.setText(f"{r['pendiente']:.2f}")
            self.parent.stack.setCurrentWidget(self.parent.tab_cobros)
        except Exception:
            pass

    def anular(self):
        data = self._fila_seleccionada()
        if not data: return
        fid, _ = data
        if not confirm(self, "¿Seguro que quieres anular esta factura? Se generará una factura rectificativa."):
            return
        conn = get_connection()
        r = conn.execute("SELECT * FROM facturas WHERE id=?", (fid,)).fetchone()
        if r["estado"] != "emitida":
            error(self, "Esta factura ya está anulada o rectificada.")
            conn.close()
            return
        # marcar anulada
        conn.execute("UPDATE facturas SET estado='anulada', estado_cobro='pagada', pendiente=0 WHERE id=?", (fid,))
        # registro de anulación
        emp = conn.execute("SELECT nif FROM empresa WHERE id=1").fetchone()
        last = conn.execute("SELECT hash_registro FROM registros_facturacion ORDER BY id DESC LIMIT 1").fetchone()
        hash_anterior = last["hash_registro"] if last else None
        from ..services.hash_chain import hash_registro_factura
        hash_reg = hash_registro_factura(r["numero"] + "-ANUL", r["fecha_emision"], emp["nif"],
                                        r["nif_receptor"] if "nif_receptor" in r.keys() else "",
                                        r["base_imponible"], r["total_factura"], hash_anterior)
        # nif receptor from cliente
        cl = conn.execute("SELECT dni_cif FROM clientes WHERE id=?", (r["cliente_id"],)).fetchone()
        nif_rec = cl["dni_cif"] if cl else ""
        hash_reg = hash_registro_factura(r["numero"] + "-ANUL", r["fecha_emision"], emp["nif"], nif_rec,
                                        r["base_imponible"], r["total_factura"], hash_anterior)
        from ..services.hash_chain import qr_payload_url
        qr_payload = qr_payload_url(r["numero"] + "-ANUL", emp["nif"], r["fecha_emision"], r["total_factura"], False)
        conn.execute("""INSERT INTO registros_facturacion (factura_id, tipo, numero_factura, fecha_emision,
                        nif_emisor, nif_receptor, base_imponible, total_factura, hash_registro,
                        hash_anterior, qr_payload) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (fid, "anulacion", r["numero"] + "-ANUL", r["fecha_emision"], emp["nif"], nif_rec,
                      r["base_imponible"], r["total_factura"], hash_reg, hash_anterior, qr_payload))
        conn.commit()
        conn.close()
        info(self, "Factura anulada. Todo correcto.")
        self.refrescar()

    def exportar(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Exportar para mi asesor", "registros_facturacion.csv",
                                             "CSV (*.csv)")
        if not path: return
        exportar_csv(__import__("pathlib").Path(path))
        info(self, "Exportación guardada. Todo correcto.")
