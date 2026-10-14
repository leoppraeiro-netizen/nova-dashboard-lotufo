-- Centro de custo da NF como chave de obra (2026-09-04).
--
-- A NF do RM traz CODCCUSTO (centro de custo), preenchido no faturamento por exigencia
-- contabil -- nao e' trabalho novo de ninguem. Para a Lotufo (coligada 1, uma so'
-- entidade com dezenas de contratos) o casamento por valor sozinho e' ambiguo entre
-- obras: duas medicoes de obras diferentes podem ter o mesmo valor. O centro de custo
-- diz de QUAL obra e' a NF, e ai' o valor desempata dentro da obra certa.
--
-- Consorcio nao precisa: a coligada ja' isola a obra (1:1, migracao 012), entao o
-- contrato do consorcio pode deixar `centro_custo_rm` NULL e o casamento continua
-- caindo no comportamento por coligada.
--
-- `centro_custo` na NF: o codigo que o RM mandou, espelho, sem normalizar (como
-- `campo_livre1`). `centro_custo_rm` no contrato: cadastro nosso, o centro de custo
-- daquela obra no RM. So' estreita o casamento quando o centro aponta para EXATAMENTE
-- UM contrato dentro da coligada -- mesma disciplina do campo livre (chave repetida
-- entre contratos nao casa sozinha).
ALTER TABLE notas_fiscais ADD COLUMN centro_custo TEXT;
ALTER TABLE contratos ADD COLUMN centro_custo_rm TEXT;
