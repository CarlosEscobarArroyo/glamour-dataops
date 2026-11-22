-- Productos con su categoría y subcategoría.
--
-- La clasificación sale de dos fuentes, en este orden:
--   1. La sección del catálogo donde el negocio colocó el producto (Blusas,
--      Calzado, ...). Es un dato real del origen, pero solo lo tiene menos de la
--      mitad de los productos.
--   2. Si no tiene sección, las palabras de su nombre. Se aplica la primera regla
--      que coincide, en el orden escrito.
-- fuente_categoria indica cuál de las dos se usó.
CREATE OR REPLACE TABLE bq_validation.dim_producto AS
WITH seccion_categoria AS (
  -- Categoría que corresponde a cada sección del catálogo. Las secciones que no
  -- están aquí (páginas web, o secciones sin equivalente claro) no clasifican.
  SELECT * FROM UNNEST([
    STRUCT('12172819720200000000' AS id_seccion, 'Ropa' AS categoria, 'Blusas' AS subcategoria),  -- Blusas
    ('12172819720100000000', 'Ropa', 'Vestidos'),  -- Vestidos
    ('12172819723900000000', 'Ropa', 'Vestidos'),  -- POLIVESTIDO
    ('12172819720500000000', 'Ropa', 'Chaquetas'),  -- Chaquetas
    ('12172819721100000000', 'Ropa', 'Polos'),  -- Polos
    ('12172819720300000000', 'Ropa', 'Pantalones'),  -- Pantalones
    ('12172819720600000000', 'Ropa', 'Enterizos'),  -- Enterizos
    ('12172819721000000000', 'Ropa', 'Camisas'),  -- Camisas
    ('12172819721500000000', 'Ropa', 'Conjuntos'),  -- Conjunto Deportivo
    ('12172819720700000000', 'Ropa', 'Conjuntos'),  -- Conjunto dos piezas
    ('12172819721900000000', 'Ropa', 'Shorts'),  -- Short
    ('12172819724800000000', 'Ropa', 'Poleras'),  -- POLERA
    ('12172819720400000000', 'Ropa', 'Poleras'),  -- Chompera
    ('12172819723700000000', 'Ropa', 'Casacas'),  -- CASACA
    ('12172819724000000000', 'Ropa', 'Básicos'),  -- CAMISETA
    ('12172819721300000000', 'Ropa', 'Faldas'),  -- Falda
    ('12172819720900000000', 'Ropa', 'Tops'),  -- Top
    ('12172819721600000000', 'Ropa', 'Batolas'),  -- Batola
    ('12172819721400000000', 'Ropa', 'Capas'),  -- Capa
    ('12172819723500000000', 'Ropa', 'Capas'),  -- KIMONO
    ('12172819721800000000', 'Ropa', 'Capris'),  -- Capri
    ('12172819723200000000', 'Ropa', 'Leggins'),  -- LEGIN
    ('12172819723300000000', 'Ropa', 'Abrigos'),  -- ABRIGO
    ('12172819723600000000', 'Ropa', 'Cardigans'),  -- CARDIGAN
    ('12172819723400000000', 'Ropa', 'Chalecos'),  -- CHALECO
    ('12172819723800000000', 'Ropa', 'Pijamas'),  -- PIJAMA
    ('12172819721700000000', 'Ropa', 'Pijamas'),  -- Pijama Short
    ('12172819724100000000', 'Ropa', 'Bikini'),  -- BIKINI
    ('12172819724400000000', 'Ropa', 'Lencería'),  -- BABY DOLL
    ('12172819724500000000', 'Ropa', 'Lencería'),  -- BRASIER
    ('12172819724300000000', 'Ropa', 'Lencería'),  -- PANTY
    ('12172819725200000000', 'Ropa', 'Calzado'),  -- Calzado
    ('12172819725200020000', 'Ropa', 'Calzado'),  -- Sandalias
    ('12172819725200010000', 'Ropa', 'Calzado'),  -- Botines
    ('12172819722000000000', 'Ropa', 'Calzado'),  -- SNIKERS
    ('12172819724900000000', 'Accesorios', 'Carteras'),  -- CARTERA
    ('12172819722100000000', 'Accesorios', 'Lentes'),  -- LENTES
    ('12172819721200000000', 'Regalos / Incentivos', 'Regalos')  -- PREMIOS
  ])
),
por_seccion AS (
  -- Si un producto está en varias secciones, se toma la más específica.
  SELECT
    pertenece.ccodcontenido AS id_producto,
    equivalencia.categoria,
    equivalencia.subcategoria
  FROM bq_staging.seccioncontenido AS pertenece
  JOIN bq_staging.seccion AS seccion USING (ccodseccion)
  JOIN seccion_categoria AS equivalencia
    ON equivalencia.id_seccion = seccion.ccodseccion
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY pertenece.ccodcontenido
    ORDER BY seccion.cnivseccion DESC, seccion.ccodseccion
  ) = 1
),
producto AS (
  -- Las reglas buscan en el nombre en minúsculas; el nombre que se guarda es el
  -- original, tal como está escrito en el sistema, sin espacios sobrantes.
  SELECT
    ccodcontenido AS id_producto,
    TRIM(cnomcontenido) AS nombre_producto,
    LOWER(TRIM(IFNULL(cnomcontenido, ''))) AS nombre
  FROM bq_staging.contenido
),
por_nombre AS (
  SELECT
    id_producto,
    nombre_producto,
    CASE
      WHEN REGEXP_CONTAINS(nombre, r'blusa|vestido|saco|pantalon|pantalón|camiseta|básico|tshirt|sueter|sweater|batola|camisilla|chaleco|chaqueta|chompa|chompero|chompera|chauqueta|conjunto|enterizo|polo|camisa|top|leggin|short|capri|kimono|cardigan|abrigo|pijama|capa|casaca|botines|sandalias|sandalia|zapatillas|zapatos|zapato|sniker|falda|faldon|jean|pantalaon|bikini|baby doll|brasier|panty|mandil|polera|ballerinas|botin|pantufla|camison|blazer|bata') THEN 'Ropa'
      WHEN REGEXP_CONTAINS(nombre, r'labial|lipgloss|lipstick|lipstisk|rubor|delineador|rimel|cejas|sombras|polvo|corrector|brochas|base liquida|rizador|tinta de labios') THEN 'Maquillaje'
      WHEN REGEXP_CONTAINS(nombre, r'perfume|esz|kp|insp|herod|marly') THEN 'Perfumes'
      WHEN REGEXP_CONTAINS(nombre, r'arete|collar|anillo|morral|cartera|bolsa|lentes|reloj|correa|mascarilla|cubretodo|pulsera|tobillera|monederos|mochil|billetera|portacelular|bisuteria') THEN 'Accesorios'
      WHEN REGEXP_CONTAINS(nombre, r'horno|parrilla|olla|fuente|jarra|taza|dulcera|plato|vaso|termo|copas|vajilla|moldes|portacucharas|cocina|secadora|electrodomesticos|plancha|miniplancha|exprimidor|microondas|harina|batidor|jarrita|taper|salero|lampara|papelero|herramienta|frigobar|tv|espejo|humidificador') THEN 'Electrodomésticos'
      WHEN REGEXP_CONTAINS(nombre, r'audifono|audífono|parlante|radio') THEN 'Tecnología'
      WHEN REGEXP_CONTAINS(nombre, r'manta|mantel|sombrilla|salida de cama') THEN 'Hogar'
      WHEN REGEXP_CONTAINS(nombre, r'regalo|cartuchera|gana|promocion|pc|premio') THEN 'Regalos / Incentivos'
      WHEN REGEXP_CONTAINS(nombre, r'ae') THEN 'Aceites Esenciales'
      ELSE 'Sin clasificar'
    END AS categoria,
    CASE
      WHEN REGEXP_CONTAINS(nombre, r'pc|premio') THEN 'Regalos'
      WHEN REGEXP_CONTAINS(nombre, r'blusa') THEN 'Blusas'
      WHEN REGEXP_CONTAINS(nombre, r'vestido') THEN 'Vestidos'
      WHEN REGEXP_CONTAINS(nombre, r'saco') THEN 'Sacos'
      WHEN REGEXP_CONTAINS(nombre, r'pantalon|pantalón|jeans|pantalaon|jean') THEN 'Pantalones'
      WHEN REGEXP_CONTAINS(nombre, r'básico|camiseta') THEN 'Básicos'
      WHEN REGEXP_CONTAINS(nombre, r'batola') THEN 'Batolas'
      WHEN REGEXP_CONTAINS(nombre, r'camisilla') THEN 'Camisillas'
      WHEN REGEXP_CONTAINS(nombre, r'chaleco') THEN 'Chalecos'
      WHEN REGEXP_CONTAINS(nombre, r'chaqueta|chauqueta') THEN 'Chaquetas'
      WHEN REGEXP_CONTAINS(nombre, r'conjunto') THEN 'Conjuntos'
      WHEN REGEXP_CONTAINS(nombre, r'enterizo') THEN 'Enterizos'
      WHEN REGEXP_CONTAINS(nombre, r'polo') THEN 'Polos'
      WHEN REGEXP_CONTAINS(nombre, r'camisa') THEN 'Camisas'
      WHEN REGEXP_CONTAINS(nombre, r'top') THEN 'Tops'
      WHEN REGEXP_CONTAINS(nombre, r'leggin') THEN 'Leggins'
      WHEN REGEXP_CONTAINS(nombre, r'short') THEN 'Shorts'
      WHEN REGEXP_CONTAINS(nombre, r'capri') THEN 'Capris'
      WHEN REGEXP_CONTAINS(nombre, r'chompa') THEN 'Chompas'
      WHEN REGEXP_CONTAINS(nombre, r'kimono|capa') THEN 'Capas'
      WHEN REGEXP_CONTAINS(nombre, r'cardigan') THEN 'Cardigans'
      WHEN REGEXP_CONTAINS(nombre, r'abrigo') THEN 'Abrigos'
      WHEN REGEXP_CONTAINS(nombre, r'pijama|camison') THEN 'Pijamas'
      WHEN REGEXP_CONTAINS(nombre, r'labial|lipgloss|lipstick') THEN 'Labios'
      WHEN REGEXP_CONTAINS(nombre, r'rubor') THEN 'Rubor'
      WHEN REGEXP_CONTAINS(nombre, r'delineador|rimel|sombras') THEN 'Ojos'
      WHEN REGEXP_CONTAINS(nombre, r'cejas') THEN 'Cejas'
      WHEN REGEXP_CONTAINS(nombre, r'polvo') THEN 'Polvo'
      WHEN REGEXP_CONTAINS(nombre, r'corrector') THEN 'Corrector'
      WHEN REGEXP_CONTAINS(nombre, r'brochas') THEN 'Brochas'
      WHEN REGEXP_CONTAINS(nombre, r'arete') THEN 'Aretes'
      WHEN REGEXP_CONTAINS(nombre, r'collar') THEN 'Collares'
      WHEN REGEXP_CONTAINS(nombre, r'anillo') THEN 'Anillos'
      WHEN REGEXP_CONTAINS(nombre, r'morral|mochil|cartera|bolsa') THEN 'Carteras'
      WHEN REGEXP_CONTAINS(nombre, r'lentes') THEN 'Lentes'
      WHEN REGEXP_CONTAINS(nombre, r'reloj') THEN 'Relojes'
      WHEN REGEXP_CONTAINS(nombre, r'correa') THEN 'Correas'
      WHEN REGEXP_CONTAINS(nombre, r'mascarilla') THEN 'Mascarillas'
      WHEN REGEXP_CONTAINS(nombre, r'cubretodo') THEN 'Cubretodo'
      WHEN REGEXP_CONTAINS(nombre, r'pulsera') THEN 'Pulseras'
      WHEN REGEXP_CONTAINS(nombre, r'tobillera') THEN 'Tobilleras'
      WHEN REGEXP_CONTAINS(nombre, r'monederos|billetera|portacelular|mandil') THEN 'Otros'
      WHEN REGEXP_CONTAINS(nombre, r'toalla|sabana|edredón|portaretrato|lampara|papelero|herramienta|tv|espejo') THEN 'Hogar'
      WHEN REGEXP_CONTAINS(nombre, r'jarra|taza|dulcera|plato|vaso|termo|olla|horno|parrilla|fuente|copas|vajilla|moldes|portacucharas|cocina|frigobar|exprimidor|microondas|harina|batidor|jarrita|taper|salero') THEN 'Cocina'
      WHEN REGEXP_CONTAINS(nombre, r'secadora|electrodomesticos|plancha|miniplancha') THEN 'Sin subcategoría'
      WHEN REGEXP_CONTAINS(nombre, r'botines|sandalias|zapatillas|zapatos|sniker|sandalia|botin|ballerinas|pantufla|zapato') THEN 'Calzado'
      WHEN REGEXP_CONTAINS(nombre, r'falda|faldon') THEN 'Faldas'
      WHEN REGEXP_CONTAINS(nombre, r'bikini') THEN 'Bikini'
      WHEN REGEXP_CONTAINS(nombre, r'baby doll|brasier|panty') THEN 'Lencería'
      WHEN REGEXP_CONTAINS(nombre, r'polera|chompera') THEN 'Poleras'
      WHEN REGEXP_CONTAINS(nombre, r'esz') THEN 'Masculino'
      WHEN REGEXP_CONTAINS(nombre, r'kp') THEN 'Femenino'
      WHEN REGEXP_CONTAINS(nombre, r'blazer') THEN 'Blazer'
      WHEN REGEXP_CONTAINS(nombre, r'bata') THEN 'Bata'
      WHEN REGEXP_CONTAINS(nombre, r'ae') THEN 'Aceites Esenciales'
      WHEN REGEXP_CONTAINS(nombre, r'casaca') THEN 'Casacas'
      ELSE 'Sin subcategoría'
    END AS subcategoria
  FROM producto
)
SELECT
  por_nombre.id_producto,
  por_nombre.nombre_producto,
  IFNULL(por_seccion.categoria, por_nombre.categoria) AS categoria,
  IFNULL(por_seccion.subcategoria, por_nombre.subcategoria) AS subcategoria,
  CASE
    WHEN por_seccion.id_producto IS NOT NULL THEN 'Sección del catálogo'
    WHEN por_nombre.categoria != 'Sin clasificar' THEN 'Nombre del producto'
    ELSE 'Sin clasificar'
  END AS fuente_categoria
FROM por_nombre
LEFT JOIN por_seccion USING (id_producto);
