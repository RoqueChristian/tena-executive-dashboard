SELECT
    codfornec AS cod_fornecedor,
    fornecedor AS nm_fornecedor,
    cgc AS cnpj_fornecedor,
    fantasia AS nm_fornecedor_fantasia,
    CASE 
         WHEN classificacao = 'F' THEN 'Farma'
         WHEN classificacao = 'H' THEN 'HB'
         ELSE 'Outros'
     END AS classificacao
FROM pcfornec
WHERE codfornec = 77800