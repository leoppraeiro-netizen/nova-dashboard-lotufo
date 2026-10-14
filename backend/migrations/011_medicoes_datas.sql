-- Fase 3,5: datas dos marcos DEPOIS do protocolo. A spec §6 define os eixos
-- temporais dos indicadores -- Emitido = emissao da NF, Recebido = data da baixa --
-- e ate aqui a medicao guardava so' o ESTADO, sem a data em que entrou nele; o
-- atesto (glosa registrada pelo orgao) tambem nao tinha data. Sem elas, "dias parados
-- no orgao" e "a receber ha' quanto tempo" nao se calculam.
--
-- Todas opcionais e sem migracao de dado: medicao antiga fica com NULL (data
-- desconhecida), e o painel diz "sem data" em vez de inventar uma. Quando a fase 5
-- ligar o RM, e' nestas colunas que a emissao e a baixa detectadas entram.
ALTER TABLE medicoes ADD COLUMN atestado_em TEXT;
ALTER TABLE medicoes ADD COLUMN nf_emitida_em TEXT;
ALTER TABLE medicoes ADD COLUMN recebida_em TEXT;
