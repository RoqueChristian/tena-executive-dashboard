WITH RawData AS (
    SELECT
        cli.codcli,
        cli.cliente,
        COALESCE(NULLIF(TRIM(cli.fantasia), ''), cli.cliente) AS fantasia,
        cli.codcliprinc,
        cid.uf,
        cid.nomecidade,
        REGEXP_REPLACE(TRIM(cli.cgcent), '[^0-9]', '') AS documento_bruto
    FROM pcclient cli
    LEFT JOIN pccidade cid ON cid.uf = cli.estent AND cid.codcidade = cli.codcidade
    
)
SELECT
    codcli AS cod_cliente,
    cliente AS nm_cliente,
    fantasia AS nm_cliente_fantasia,
    codcliprinc AS cod_cliente_princ,
    uf,
    nomecidade AS nm_cidade,
    CASE 
        WHEN LENGTH(documento_bruto) <= 11 THEN LPAD(documento_bruto, 11, '0')
        ELSE LPAD(documento_bruto, 14, '0')
    END AS cnpj_cliente,
    CASE 
        WHEN LENGTH(documento_bruto) <= 11 THEN 'CPF'
        ELSE 'CNPJ'
    END AS tp_documento
FROM RawData