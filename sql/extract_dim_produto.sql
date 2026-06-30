SELECT 
  PCPRODUT.CODPROD AS cod_produto,
  PCPRODUT.codprodprinc AS cod_produto_princ,
  PCPRODUT.codauxiliar AS cod_ean,
  PCPRODUT.DESCRICAO AS desc_produto,
  NVL(TRIM(PCCATEGORIA.CATEGORIA), 'Não cadastrado') AS categoria,
  NVL(TRIM(PCSECAO.DESCRICAO), 'Não cadastrado') AS secao,
  NVL(TRIM(PCDEPTO.DESCRICAO), 'Não cadastrado') AS departamento,
  NVL(PCPRODUT.CODMARCA, 0) AS cod_marca,
  NVL(TRIM(PCMARCA.MARCA), 'Não cadastrado') AS marca
FROM PCPRODUT
LEFT JOIN pcdepto ON pcdepto.CODEPTO = PCPRODUT.CODEPTO
LEFT JOIN PCSECAO ON PCSECAO.CODSEC = PCPRODUT.CODSEC AND pcsecao.codepto = pcdepto.codepto
LEFT JOIN pccategoria ON pccategoria.CODCATEGORIA = PCPRODUT.CODCATEGORIA AND pccategoria.codsec = pcsecao.codsec
LEFT JOIN PCMARCA ON PCPRODUT.CODMARCA = PCMARCA.CODMARCA
WHERE
     pcprodut.dtexclusao IS NULL AND PCPRODUT.CODFORNEC = 77800 AND UPPER(TRIM(PCCATEGORIA.CATEGORIA)) NOT IN ('BRINDES')
ORDER BY
    pcprodut.CODPROD