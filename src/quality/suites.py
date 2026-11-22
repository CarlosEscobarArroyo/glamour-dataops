"""Contratos de calidad del modelo dimensional.

Todas las tablas reciben controles estructurales. El piloto agrega controles de
negocio a dim_fecha, dim_campana, dim_ubicacion, dim_vendedor y fact_pedidos.
"""

from dataclasses import dataclass
from typing import Callable


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


def _unexpected_rows(gxe, query: str, description: str):
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
            "La fecha inicial de una campaña no puede ser posterior a su fecha final.",
        ),
    ]


def _dim_ubicacion(gxe, _qualified: Callable[[str], str]) -> list:
    return [
        gxe.ExpectColumnValuesToNotBeNull(column="distrito"),
        gxe.ExpectColumnValuesToNotBeNull(column="provincia"),
        gxe.ExpectColumnValuesToNotBeNull(column="departamento"),
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
                "Cada pedido debe corresponder a una vendedora existente.",
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
        ]
    )
    return expectations


PILOT_BUILDERS = {
    "dim_fecha": _dim_fecha,
    "dim_campana": _dim_campana,
    "dim_ubicacion": _dim_ubicacion,
    "dim_vendedor": _dim_vendedor,
    "fact_pedidos": _fact_pedidos,
}


def build_expectations(gxe, table: str, project: str, dataset: str) -> list:
    """Devuelve las expectativas bloqueantes de una tabla."""
    contract = TABLE_CONTRACTS[table]

    def qualified(other_table: str) -> str:
        return f"`{project}.{dataset}.{other_table}`"

    expectations = _structural_expectations(gxe, contract)
    builder = PILOT_BUILDERS.get(table)
    if builder:
        expectations.extend(builder(gxe, qualified))
    return expectations
