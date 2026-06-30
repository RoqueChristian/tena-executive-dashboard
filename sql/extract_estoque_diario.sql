WITH cte_dias_zerados AS (
    SELECT 
        h.codfilial,
        h.codprod,
        SUM(CASE WHEN NVL(h.qtestger, 0) <= 0 THEN 1 ELSE 0 END) AS dz_90d
    FROM pchistest h
    INNER JOIN pcprodut p ON p.codprod = h.codprod
    WHERE h.data >= TRUNC(SYSDATE) - 91
      AND h.data < TRUNC(SYSDATE) - 1 
      AND p.codfornec = 77800
      AND h.codfilial = 3
      AND p.dtexclusao IS NULL
      AND p.codcategoria <> 100061
    GROUP BY h.codfilial, h.codprod
)
SELECT
    he.codfilial AS cod_filial,
    TRUNC(he.data) AS dt_estoque,
    he.codprod AS cod_produto,
    (NVL(he.qtestger, 0) - NVL(he.qtbloqueada, 0)) AS qtd_estoque,
    ROUND(he.custorep, 2) AS valor_ultima_entrada,
    f.codcomprador AS cod_comprador,
    ep.nome AS comprador,
    f.codfornec AS cod_fornecedor,
    NVL(dz.dz_90d, 0) AS dias_zerados_90d
FROM pchistest he
INNER JOIN pcprodut p ON p.codprod = he.codprod
INNER JOIN pcfornec f ON f.codfornec = p.codfornec
LEFT JOIN pcempr ep ON ep.matricula = f.codcomprador
LEFT JOIN cte_dias_zerados dz ON dz.codfilial = he.codfilial AND dz.codprod = he.codprod
WHERE 
    TRUNC(he.data) = TRUNC(SYSDATE) - 1  
    AND f.codfornec = 77800
    AND he.codfilial = 3
    AND (NVL(he.qtestger, 0) - NVL(he.qtbloqueada, 0)) > 0
    AND p.dtexclusao IS NULL
    AND p.codcategoria <> 100061
ORDER BY he.codprod
