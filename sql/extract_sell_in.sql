SELECT
    pedido.codfilial AS cod_filial,
    pedido.numped AS numero_pedido,
    pedido.dtemissao AS dt_emissao,
    pedido.dtfatur AS dt_faturamento,
    pedido.dtembarque AS dt_embarque,
    pedido.codfornec AS cod_fornecedor,
    item.codprod AS cod_produto,
    item.qtpedida AS qt_pedida,
    item.qtentregue AS qt_entregue,
    item.pcompra AS preco_compra
FROM pcpedido pedido
INNER JOIN pcitem item ON pedido.numped = item.numped
WHERE codfornec = 77800
    AND codfilial = 3 
AND dtemissao > to_date('01/01/2026','DD/MM/YYYY')