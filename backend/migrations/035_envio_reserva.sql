-- 035: reserva do envio ANTES do e-mail (testes de quebra de 10/10/2026, A-01/A-02). A checagem "ja' enviado?"
-- era leitura solta e o `enviado` so' era gravado depois do e-mail (segundos): tres cliques simultaneos mandavam
-- tres e-mails ao orgao/faturamento. Agora quem envia reserva a linha numa transacao (BEGIN IMMEDIATE) e so'
-- entao manda; o outro recebe "envio em andamento". Reserva presa nao expira: so' sai por liberacao manual
-- auditada, depois de conferir a caixa de Enviados. Ver app/envio_reserva.py.
ALTER TABLE protocolos ADD COLUMN envio_reservado_em TEXT;
ALTER TABLE protocolos ADD COLUMN envio_reservado_por INTEGER REFERENCES usuarios(id);
ALTER TABLE espelhos ADD COLUMN envio_reservado_em TEXT;
ALTER TABLE espelhos ADD COLUMN envio_reservado_por INTEGER REFERENCES usuarios(id);
ALTER TABLE pleitos ADD COLUMN envio_reservado_em TEXT;
ALTER TABLE pleitos ADD COLUMN envio_reservado_por INTEGER REFERENCES usuarios(id);
