SELECT
     mov.codfilial AS cod_filial,
     mov.dtmov AS dt_venda,
     mov.codcli AS cod_cliente,
     mov.codprod AS cod_produto,
     CASE WHEN mov.codoper = 'S' THEN mov.qt ELSE 0 END as qtd_vendida,
     CASE WHEN mov.codoper = 'S' THEN ROUND(mov.qt * mov.punit, 2) ELSE 0 END as vl_total_vendido,
     CASE WHEN mov.codoper = 'ED' THEN mov.qt ELSE 0 END as qtd_devolvida,
     CASE WHEN mov.codoper = 'ED' THEN ROUND(mov.qt * mov.punit, 2) ELSE 0 END as vl_total_devolvido,
     CASE
        WHEN ped.TIPOFV = 'PE' AND ped.ORIGEMPED = 'F' THEN 'PEDIDO ELETRÔNICO'
        WHEN ped.TIPOFV != 'PE' AND ped.TIPOFV  = 'OL' AND ped.ORIGEMPED = 'F' THEN 'OPERADOR LOGÍSTICO'
        WHEN ped.TIPOFV IS NULL  AND ped.ORIGEMPED = 'F' THEN 'FORÇA DE VENDAS'
        WHEN ped.ORIGEMPED = 'T' THEN 'TELEMARKETING'
        WHEN ped.ORIGEMPED = 'W' THEN 'E-COMMERCE' 
        ELSE 'OUTROS' 
     END AS origem_pedido,
     CASE WHEN mov.codoper = 'S' THEN 'venda'
        WHEN mov.codoper = 'ED' THEN 'devolucao' 
        ELSE 'outros'
     END AS operacao
 FROM pcmov mov
 LEFT JOIN pcpedc ped ON ped.numped = mov.numped
 WHERE mov.codoper IN ('S', 'ED')
 AND mov.dtmov >= TO_DATE('01/01/2026','DD/MM/YYYY') 
 AND mov.dtcancel IS NULL
 AND mov.codfornec = 77800
 AND mov.codfilial = 3