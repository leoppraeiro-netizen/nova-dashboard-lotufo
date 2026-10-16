-- 037: pecas que o orgao pede no pleito de reajuste (issue #50). O apostilamento do reajuste anual da Prefeitura de
-- Cuiaba pede certidao de falencia, contrato social, documento do representante e balanco; o orgao declara isso no
-- cadastro (`pecas_pleito_reajuste`) e a operacao anexa cada peca no pleito. So' o CHECK de `tipo` muda; o resto da
-- tabela e' o da 026.
--
-- Receita oficial do SQLite para mudar CHECK (a mesma da 020 e da 033): criar nova, copiar, apagar a antiga,
-- renomear. Ninguem referencia pleito_anexos; foreign_keys OFF so' por garantia (o runner religa mesmo se falhar).
-- Reexecutavel: a `_nova` e' apagada antes de recriar. A troca roda numa transacao (o runner usa executescript, que
-- nao abre uma): se o processo cair entre o DROP e o RENAME, nada fica pela metade e a proxima execucao encontra a
-- tabela original. O PRAGMA fica fora da transacao porque dentro dela o SQLite o ignora.
PRAGMA foreign_keys=OFF;
BEGIN;

DROP TABLE IF EXISTS pleito_anexos_nova;
CREATE TABLE pleito_anexos_nova (
    id INTEGER PRIMARY KEY,
    pleito_id INTEGER NOT NULL REFERENCES pleitos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('planilha_calculo','cronograma','outro','falencia','contrato_social',
                                       'documento_representante','balanco')),
    nome TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    ext TEXT NOT NULL CHECK (ext IN ('pdf','xlsx')),
    removido_em TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO pleito_anexos_nova (id, pleito_id, tipo, nome, arquivo, sha256, tamanho, ext, removido_em, criado_em)
    SELECT id, pleito_id, tipo, nome, arquivo, sha256, tamanho, ext, removido_em, criado_em FROM pleito_anexos;
DROP TABLE pleito_anexos;
ALTER TABLE pleito_anexos_nova RENAME TO pleito_anexos;
COMMIT;

PRAGMA foreign_keys=ON;
