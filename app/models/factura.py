# app/models/factura.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class LineaFactura:
    concepto: str = ""
    cantidad: float = 1.0
    importe_base: float = 0.0       # unitario sin IVA
    porcentaje_iva: float = 21.0
    descuento: float = 0.0          # descuento en %
    porcentaje_recargo: float = 0.0  # recargo de equivalencia en %
    producto_id: Optional[int] = None
    tipo_iva_id: Optional[int] = None
    # calculados
    base_linea: float = 0.0
    iva_linea: float = 0.0
    recargo_linea: float = 0.0
    total_linea: float = 0.0

    def recalcular(self):
        base = self.cantidad * self.importe_base * (1 - (self.descuento or 0.0) / 100.0)
        self.base_linea = round(base, 2)
        self.iva_linea = round(self.base_linea * self.porcentaje_iva / 100.0, 2)
        self.recargo_linea = round(self.base_linea * (self.porcentaje_recargo or 0.0) / 100.0, 2)
        self.total_linea = round(self.base_linea + self.iva_linea + self.recargo_linea, 2)

@dataclass
class Factura:
    id: Optional[int] = None
    numero: str = ""
    fecha_emision: str = ""
    cliente_id: Optional[int] = None
    contacto_fact_id: Optional[int] = None
    lineas: list = field(default_factory=list)
    base_imponible: float = 0.0
    total_iva: float = 0.0
    total_factura: float = 0.0
    desglose_iva: dict = field(default_factory=dict)  # {pct: (base, cuota)}
    estado: str = "emitida"
    estado_cobro: str = "no_cobrada"
    pendiente: float = 0.0
    irpf_porcentaje: float = 0.0
    irpf_importe: float = 0.0
    recargo_importe: float = 0.0
    total_a_pagar: float = 0.0
    cobros: list = field(default_factory=list)  # lista de dicts: fecha, importe, forma_pago
    pdf_path: Optional[str] = None
    hash_registro: str = ""
    hash_anterior: Optional[str] = None
    factura_original_id: Optional[int] = None
    motivo_rectificacion: Optional[str] = None

    def recalcular_totales(self):
        self.base_imponible = round(sum(l.base_linea for l in self.lineas), 2)
        self.total_iva = round(sum(l.iva_linea for l in self.lineas), 2)
        self.total_factura = round(self.base_imponible + self.total_iva, 2)
        self.pendiente = self.total_factura
        self.irpf_importe = round(self.base_imponible * (self.irpf_porcentaje or 0.0) / 100.0, 2)
        self.recargo_importe = round(sum(l.recargo_linea for l in self.lineas), 2)
        self.total_a_pagar = round(self.total_factura - self.irpf_importe, 2)
        # desglose por tipo de IVA
        d = {}
        for l in self.lineas:
            pct = l.porcentaje_iva
            if pct not in d:
                d[pct] = [0.0, 0.0]
            d[pct][0] = round(d[pct][0] + l.base_linea, 2)
            d[pct][1] = round(d[pct][1] + l.iva_linea, 2)
        self.desglose_iva = {k: (v[0], v[1]) for k, v in d.items()}
