# app/services/pdf_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os

def _estilos():
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=18, spaceAfter=6)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=11, leading=14)
    return title, normal

def _bloque_factura(story, factura, empresa, cliente, lineas, desglose, qr_path, title, normal):
    # Cabecera empresa
    if empresa.logo_path and os.path.exists(empresa.logo_path):
        story.append(Image(empresa.logo_path, width=40*mm, height=20*mm))
    story.append(Paragraph(f"<b>{empresa.nombre}</b>", title))
    story.append(Paragraph(f"NIF: {empresa.nif}", normal))
    story.append(Paragraph(f"{empresa.direccion}, {empresa.cp} {empresa.ciudad}", normal))
    story.append(Paragraph(f"{empresa.comunidad_autonoma}, {empresa.pais}", normal))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph(f"<b>FACTURA Nº {factura.numero}</b>", title))
    story.append(Paragraph(f"Fecha: {factura.fecha_emision}", normal))
    story.append(Spacer(1, 4*mm))

    # Cliente
    story.append(Paragraph("<b>Cliente:</b>", normal))
    nombre_cli = cliente.nombre_mostrar() if hasattr(cliente, "nombre_mostrar") else (cliente.get("nombre","") if hasattr(cliente,"get") else str(cliente))
    story.append(Paragraph(nombre_cli, normal))
    dni = cliente.dni_cif if hasattr(cliente, "dni_cif") else (cliente.get("dni_cif", "") if hasattr(cliente, "get") else "")
    story.append(Paragraph(f"NIF/CIF: {dni}", normal))
    dir_ = cliente.direccion if hasattr(cliente, "direccion") else (cliente.get("direccion", "") if hasattr(cliente, "get") else "")
    cp = cliente.cp if hasattr(cliente, "cp") else (cliente.get("cp", "") if hasattr(cliente, "get") else "")
    ciudad = cliente.ciudad if hasattr(cliente, "ciudad") else (cliente.get("ciudad", "") if hasattr(cliente, "get") else "")
    story.append(Paragraph(f"{dir_}, {cp} {ciudad}", normal))
    story.append(Spacer(1, 6*mm))

    # Tabla de líneas
    data = [["Concepto", "Cant.", "Precio", "Dto.%", "IVA %", "Total"]]
    total_descuento = 0.0
    for l in lineas:
        desc = getattr(l, "descuento", 0.0) or 0.0
        total_descuento += l.cantidad * l.importe_base * desc / 100.0
        data.append([l.concepto, f"{l.cantidad:g}", f"{l.importe_base:.2f} €",
                    f"{desc:g}%", f"{l.porcentaje_iva:.0f}%", f"{l.total_linea:.2f} €"])
    t = Table(data, colWidths=[60*mm, 15*mm, 22*mm, 18*mm, 18*mm, 25*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

    # Desglose IVA
    story.append(Paragraph("<b>Desglose de IVA:</b>", normal))
    for pct, (base, cuota) in desglose.items():
        story.append(Paragraph(f"IVA {pct:.0f}%: base {base:.2f} € + cuota {cuota:.2f} €", normal))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(f"<b>Base imponible total: {factura.base_imponible:.2f} €</b>", normal))
    story.append(Paragraph(f"<b>Total descuento: {total_descuento:.2f} €</b>", normal))
    story.append(Paragraph(f"<b>Total factura: {factura.total_factura:.2f} €</b>", title))
    rec_imp = getattr(factura, "recargo_importe", 0.0) or 0.0
    if rec_imp and rec_imp > 0:
        story.append(Paragraph(f"Recargo de equivalencia: {rec_imp:.2f} €", normal))
    irpf_pct = getattr(factura, "irpf_porcentaje", 0.0) or 0.0
    irpf_imp = getattr(factura, "irpf_importe", 0.0) or 0.0
    if irpf_pct and irpf_pct > 0:
        story.append(Paragraph(f"Retención IRPF ({irpf_pct:g}%): -{irpf_imp:.2f} €", normal))
        total_pagar = getattr(factura, "total_a_pagar", None)
        if total_pagar is None:
            total_pagar = factura.total_factura - irpf_imp
        story.append(Paragraph(f"<b>Total a pagar: {total_pagar:.2f} €</b>", title))

    # Cobros
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("<b>Cobros:</b>", normal))
    estado = getattr(factura, "estado_cobro", "no_cobrada") or "no_cobrada"
    etiqueta_estado = {"pagada": "Pagada", "parcial": "Parcial", "no_cobrada": "Pendiente"}.get(estado, estado)
    pendiente = getattr(factura, "pendiente", 0.0) or 0.0
    story.append(Paragraph(f"Estado de cobro: {etiqueta_estado}", normal))
    story.append(Paragraph(f"Pendiente de cobro: {pendiente:.2f} €", normal))
    cobros = getattr(factura, "cobros", None) or []
    if cobros:
        data_c = [["Fecha", "Importe", "Forma de pago"]]
        for c in cobros:
            data_c.append([str(c.get("fecha", c.get("fecha_cobro", ""))),
                          f"{float(c.get('importe', 0)):.2f} €",
                          str(c.get("forma_pago", c.get("forma", "")))])
        tc = Table(data_c, colWidths=[40*mm, 30*mm, 60*mm])
        tc.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("FONTSIZE", (0,0), (-1,-1), 9),
        ]))
        story.append(tc)
    else:
        story.append(Paragraph("Sin cobros registrados.", normal))

    # Registro Mercantil
    reg = getattr(empresa, "registro_mercantil", None)
    if reg:
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(f"Registro Mercantil: {reg}", normal))

    story.append(Spacer(1, 8*mm))
    if qr_path and os.path.exists(qr_path):
        story.append(Image(qr_path, width=35*mm, height=35*mm))
        story.append(Paragraph("Código de verificación (Verifactu)", normal))

def generar_pdf_factura(factura, empresa, cliente, lineas, desglose, qr_path, destino_path) -> str:
    doc = SimpleDocTemplate(destino_path, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    title, normal = _estilos()
    story = []
    _bloque_factura(story, factura, empresa, cliente, lineas, desglose, qr_path, title, normal)
    doc.build(story)
    return destino_path

def generar_pdf_facturas(lista, destino_path) -> str:
    # lista: lista de dicts/tuplas con keys: factura, empresa, cliente, lineas, desglose, qr_path
    doc = SimpleDocTemplate(destino_path, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    title, normal = _estilos()
    story = []
    for i, item in enumerate(lista):
        if i > 0:
            story.append(PageBreak())
        _bloque_factura(story, item["factura"], item["empresa"], item["cliente"],
                        item["lineas"], item["desglose"], item["qr_path"], title, normal)
    doc.build(story)
    return destino_path
