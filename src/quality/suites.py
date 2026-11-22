"""Contratos de calidad del modelo dimensional.

Todas las tablas reciben controles estructurales. El piloto agrega controles de
negocio a dim_fecha, dim_campana, dim_ubicacion, dim_vendedor y fact_pedidos, y
su extensión a dim_producto y fact_pedidos_detalle (pilot=True en el contrato).

Cada expectativa es crítica (detiene la publicación) salvo las marcadas con
severity="warning": esas solo se reportan en Data Docs y en el log. Son
advertencias los defectos conocidos del origen que el negocio aún no corrige.
"""

from dataclasses import dataclass
from typing import Callable


WARNING = "warning"
WARNING_PREFIX = "Advertencia: "


@dataclass(frozen=True)
class TableContract:
    columns: tuple[str, ...]
    key: tuple[str, ...]
    pilot: bool = False


TABLE_CONTRACTS: dict[str, TableContract] = {
    "dim_fecha": TableContract(
        ("id_fecha", "fecha", "anio", "mes", "dia", "trimestre"),
        ("id_fecha",),
        pilot=True,
    ),
    "dim_campana": TableContract(
        (
            "id_campana",
            "nombre_campana",
            "estado",
            "fecha_inicio",
            "fecha_fin",
            "anio",
            "numero_campana",
        ),
        ("id_campana",),
        pilot=True,
    ),
    "dim_producto": TableContract(
        (
            "id_producto",
            "codigo_producto",
            "nombre_producto",
            "categoria",
            "subcategoria",
            "fuente_categoria",
        ),
        ("id_producto",),
        pilot=True,
    ),
    "dim_variante": TableContract(
        ("id_variante", "id_producto", "nombre_producto", "color", "talla"),
        ("id_variante",),
    ),
    "dim_coordinadora": TableContract(
        ("id_coordinadora", "nombre_coordinadora", "estado", "fecha_nacimiento"),
        ("id_coordinadora",),
    ),
    "dim_ubicacion": TableContract(
        ("id_ubigeo", "distrito", "provincia", "departamento", "ubigeo_inei"),
        ("id_ubigeo",),
        pilot=True,
    ),
    "dim_vendedor": TableContract(
        (
            "id_vendedor",
            "nombre_vendedor",
            "sexo",
            "fecha_nacimiento",
            "id_ubigeo",
            "celular",
            "id_lider",
            "id_coordinadora",
            "fecha_ingreso",
            "tipo_vendedor",
        ),
        ("id_vendedor",),
        pilot=True,
    ),
    "fact_pedidos": TableContract(
        (
            "id_pedido",
            "id_campana",
            "id_vendedor",
            "id_fecha",
            "id_fecha_pago",
            "id_coordinadora",
            "id_ubigeo",
            "estado_pedido",
            "monto_total_pedido",
            "monto_comision",
            "monto_envio",
            "monto_pagado",
            "es_nueva_vendedora",
            "tipo",
        ),
        ("id_pedido",),
        pilot=True,
    ),
    "fact_pedidos_detalle": TableContract(
        (
            "id_pedido",
            "id_campana",
            "id_vendedor",
            "id_fecha",
            "id_ubigeo",
            "id_pedido_detalle",
            "id_producto",
            "cantidad",
            "importe_producto",
        ),
        ("id_pedido", "id_pedido_detalle"),
        pilot=True,
    ),
    "fact_stock_actual": TableContract(
        (
            "id_variante",
            "id_producto",
            "stock",
            "stock_retenido",
            "stock_disponible",
            "stock_minimo",
            "bajo_minimo",
            "fecha_ultimo_movimiento",
        ),
        ("id_variante",),
    ),
    "fact_movimientos_stock": TableContract(
        (
            "id_movimiento",
            "id_nota",
            "id_variante",
            "id_producto",
            "id_fecha",
            "id_pedido",
            "tipo_movimiento",
            "concepto",
            "cantidad",
            "cantidad_con_signo",
            "stock_resultante",
        ),
        ("id_movimiento",),
    ),
}

PILOT_TABLES = frozenset(
    table for table, contract in TABLE_CONTRACTS.items() if contract.pilot
)


def _structural_expectations(gxe, contract: TableContract) -> list:
    expectations = [
        gxe.ExpectTableRowCountToBeBetween(
            min_value=1,
            description="La tabla construida no debe estar vacía.",
        ),
        gxe.ExpectTableColumnsToMatchSet(
            column_set=list(contract.columns),
            exact_match=True,
            description="El esquema debe coincidir con el contrato versionado.",
        ),
    ]
    for column in contract.key:
        expectations.append(
            gxe.ExpectColumnValuesToNotBeNull(
                column=column,
                description=f"La clave {column} no admite valores nulos.",
            )
        )
    if len(contract.key) == 1:
        expectations.append(
            gxe.ExpectColumnValuesToBeUnique(
                column=contract.key[0],
                description=f"La clave {contract.key[0]} identifica una sola fila.",
            )
        )
    else:
        expectations.append(
            gxe.ExpectCompoundColumnsToBeUnique(
                column_list=list(contract.key),
                description="La clave compuesta identifica una sola fila.",
            )
        )
    return expectations


def _unexpected_rows(gxe, query: str, description: str, warning: bool = False):
    if warning:
        return gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=query,
            description=WARNING_PREFIX + description,
            severity=WARNING,
        )
    return gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=query,
        description=description,
    )


def _dim_fecha(gxe, _qualified: Callable[[str], str]) -> list:
    return [
        gxe.ExpectColumnValuesToBeUnique(column="fecha"),
        gxe.ExpectColumnValuesToBeBetween(column="anio", min_value=2010, max_value=2030),
        gxe.ExpectColumnValuesToBeBetween(column="mes", min_value=1, max_value=12),
        gxe.ExpectColumnValuesToBeBetween(column="dia", min_value=1, max_value=31),
        gxe.ExpectColumnValuesToBeBetween(column="trimestre", min_value=1, max_value=4),
        _unexpected_rows(
            gxe,
            "SELECT id_fecha FROM {batch} "
            "WHERE fecha < DATE '2010-01-01' OR fecha > DATE '2030-12-31'",
            "El calendario cubre únicamente el periodo 2010-2030.",
        ),
    ]


def _dim_campana(gxe, _qualified: Callable[[str], str]) -> list:
    return [
        gxe.ExpectColumnValuesToNotBeNull(column="nombre_campana"),
        gxe.ExpectColumnValuesToNotBeNull(column="numero_campana"),
        gxe.ExpectColumnValuesToBeUnique(column="numero_campana"),
        _unexpected_rows(
            gxe,
            "SELECT id_campana FROM {batch} "
            "WHERE fecha_inicio IS NOT NULL AND fecha_fin IS NOT NULL "
            "AND fecha_inicio > fecha_fin",
            # Advertencia: una campaña del origen tiene las fechas invertidas
            # (ejecución del 22/11/2026). Corresponde agregarla a las correcciones
            # a mano de dim_campana.sql.
            "La fecha inicial de una campaña no puede ser posterior a su fecha final.",
            warning=True,
        ),
    ]


def _dim_ubicacion(gxe, _qualified: Callable[[str], str]) -> list:
    # ref_ubigeo mezcla dos niveles. Los códigos que terminan en 0000 son un país
    # (AF, BO, EC, PE000000) o un departamento (PE010000...), sin distrito ni
    # provincia. El resto son distritos y deben estar completos.
    return [
        _unexpected_rows(
            gxe,
            "SELECT id_ubigeo FROM {batch} "
            "WHERE NOT ENDS_WITH(id_ubigeo, '0000') "
            "AND (distrito IS NULL OR provincia IS NULL OR departamento IS NULL)",
            "Todo código de distrito tiene distrito, provincia y departamento.",
        ),
        # Advertencia: PE030000 llega sin departamento en ref_ubigeo.csv
        # (ejecución del 22/11/2026).
        _unexpected_rows(
            gxe,
            "SELECT id_ubigeo FROM {batch} "
            "WHERE STARTS_WITH(id_ubigeo, 'PE') AND ENDS_WITH(id_ubigeo, '0000') "
            "AND id_ubigeo != 'PE000000' AND departamento IS NULL",
            "Todo código de departamento del Perú tiene el nombre del departamento.",
            warning=True,
        ),
    ]


def _dim_vendedor(gxe, _qualified: Callable[[str], str]) -> list:
    return [
        gxe.ExpectColumnValuesToNotBeNull(column="nombre_vendedor"),
        gxe.ExpectColumnValuesToBeInSet(
            column="tipo_vendedor", value_set=["Asesora", "Líder"]
        ),
    ]


def _fact_pedidos(gxe, qualified: Callable[[str], str]) -> list:
    expectations = [
        gxe.ExpectColumnValuesToNotBeNull(column=column)
        for column in (
            "id_campana",
            "id_vendedor",
            "id_fecha",
            "estado_pedido",
            "monto_total_pedido",
            "monto_comision",
            "monto_envio",
            "monto_pagado",
            "es_nueva_vendedora",
            "tipo",
        )
    ]
    expectations.extend(
        [
            # Advertencia: fact_pedidos.sql deja pasar el código de los estados
            # que no traduce; hubo 8 pedidos así en la ejecución del 22/11/2026.
            gxe.ExpectColumnValuesToBeInSet(
                column="estado_pedido",
                value_set=[
                    "Borrador",
                    "Emitido",
                    "Pago reportado",
                    "Por Facturar",
                    "Facturado",
                    "Despachado",
                    "Entregado",
                ],
                description=WARNING_PREFIX
                + "El estado del pedido tiene un nombre conocido del sistema.",
                severity=WARNING,
            ),
            gxe.ExpectColumnValuesToBeInSet(
                column="es_nueva_vendedora", value_set=[0, 1]
            ),
            gxe.ExpectColumnValuesToBeInSet(
                column="tipo", value_set=["Directo", "Catalogo"]
            ),
            _unexpected_rows(
                gxe,
                "SELECT p.id_pedido FROM {batch} AS p "
                f"LEFT JOIN {qualified('dim_campana')} AS d "
                "ON d.id_campana = p.id_campana "
                "WHERE d.id_campana IS NULL",
                "Cada pedido debe corresponder a una campaña existente.",
            ),
            _unexpected_rows(
                gxe,
                "SELECT p.id_pedido FROM {batch} AS p "
                f"LEFT JOIN {qualified('dim_vendedor')} AS d "
                "ON d.id_vendedor = p.id_vendedor "
                "WHERE d.id_vendedor IS NULL",
                # Advertencia: dim_vendedor solo trae asesoras y líderes, y hay
                # pedidos de clientes que no existen en persona (71 el 22/11/2026).
                "Cada pedido debe corresponder a una vendedora existente.",
                warning=True,
            ),
            _unexpected_rows(
                gxe,
                "SELECT p.id_pedido FROM {batch} AS p "
                f"LEFT JOIN {qualified('dim_fecha')} AS d "
                "ON d.id_fecha = p.id_fecha "
                "WHERE d.id_fecha IS NULL",
                "La fecha de cada pedido debe existir en la dimensión calendario.",
            ),
            _unexpected_rows(
                gxe,
                "SELECT p.id_pedido FROM {batch} AS p "
                f"LEFT JOIN {qualified('dim_fecha')} AS d "
                "ON d.id_fecha = p.id_fecha_pago "
                "WHERE p.id_fecha_pago IS NOT NULL AND d.id_fecha IS NULL",
                "Toda fecha de pago informada debe existir en la dimensión calendario.",
            ),
            # id_ubigeo e id_coordinadora pueden venir vacíos (la vendedora no los
            # tiene); cuando traen un valor, debe existir en su dimensión.
            _unexpected_rows(
                gxe,
                "SELECT p.id_pedido FROM {batch} AS p "
                f"LEFT JOIN {qualified('dim_ubicacion')} AS d "
                "ON d.id_ubigeo = p.id_ubigeo "
                "WHERE p.id_ubigeo IS NOT NULL AND d.id_ubigeo IS NULL",
                "Toda ubicación informada en un pedido debe existir en dim_ubicacion.",
            ),
            _unexpected_rows(
                gxe,
                "SELECT p.id_pedido FROM {batch} AS p "
                f"LEFT JOIN {qualified('dim_coordinadora')} AS d "
                "ON d.id_coordinadora = p.id_coordinadora "
                "WHERE p.id_coordinadora IS NOT NULL AND d.id_coordinadora IS NULL",
                "Toda coordinadora informada en un pedido debe existir en dim_coordinadora.",
            ),
            # Rangos de los montos.
            _unexpected_rows(
                gxe,
                "SELECT id_pedido FROM {batch} "
                "WHERE monto_total_pedido < 0 OR monto_comision < 0 "
                "OR monto_envio < 0 OR monto_pagado < 0",
                "Los montos de un pedido no son negativos.",
            ),
            # Tolerancia de un céntimo por redondeo.
            _unexpected_rows(
                gxe,
                "SELECT id_pedido FROM {batch} "
                "WHERE ABS(monto_pagado - (monto_total_pedido - monto_comision + monto_envio)) > 0.01",
                "El monto a pagar es el de catálogo menos la comisión más el envío.",
            ),
            _unexpected_rows(
                gxe,
                "SELECT p.id_pedido FROM {batch} AS p "
                f"JOIN {qualified('dim_fecha')} AS d ON d.id_fecha = p.id_fecha "
                "WHERE d.fecha > CURRENT_DATE('America/Lima')",
                "Ningún pedido tiene fecha futura.",
            ),
        ]
    )
    return expectations


# Extensión del piloto: el detalle de pedidos y la dimensión producto.
def _dim_producto(gxe, _qualified: Callable[[str], str]) -> list:
    return [
        gxe.ExpectColumnValuesToNotBeNull(column="categoria"),
        gxe.ExpectColumnValuesToBeInSet(
            column="fuente_categoria",
            value_set=["Sección del catálogo", "Nombre del producto", "Sin clasificar"],
        ),
    ]


def _fact_pedidos_detalle(gxe, qualified: Callable[[str], str]) -> list:
    return [
        _unexpected_rows(
            gxe,
            "SELECT d.id_pedido_detalle FROM {batch} AS d "
            f"LEFT JOIN {qualified('fact_pedidos')} AS p "
            "ON p.id_pedido = d.id_pedido "
            "WHERE p.id_pedido IS NULL",
            "Cada línea de detalle pertenece a un pedido de fact_pedidos.",
        ),
        # Advertencia: el 10% del detalle apunta a productos que ya no están en
        # el catálogo, casi todos antiguos (modelo_dimensional.md).
        _unexpected_rows(
            gxe,
            "SELECT d.id_pedido_detalle FROM {batch} AS d "
            f"LEFT JOIN {qualified('dim_producto')} AS p "
            "ON p.id_producto = d.id_producto "
            "WHERE p.id_producto IS NULL",
            "Cada línea de detalle corresponde a un producto del catálogo.",
            warning=True,
        ),
    ]


PILOT_BUILDERS = {
    "dim_fecha": _dim_fecha,
    "dim_campana": _dim_campana,
    "dim_ubicacion": _dim_ubicacion,
    "dim_vendedor": _dim_vendedor,
    "fact_pedidos": _fact_pedidos,
    "dim_producto": _dim_producto,
    "fact_pedidos_detalle": _fact_pedidos_detalle,
}


def build_expectations(gxe, table: str, project: str, dataset: str) -> list:
    """Devuelve las expectativas de una tabla, críticas y de advertencia."""
    contract = TABLE_CONTRACTS[table]

    def qualified(other_table: str) -> str:
        return f"`{project}.{dataset}.{other_table}`"

    expectations = _structural_expectations(gxe, contract)
    builder = PILOT_BUILDERS.get(table)
    if builder:
        expectations.extend(builder(gxe, qualified))
    return expectations
