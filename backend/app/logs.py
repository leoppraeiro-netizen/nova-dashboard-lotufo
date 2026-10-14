"""Logs em arquivo quando `DASH_LOG_DIR` esta definida (producao).

Sem a variavel nada muda: o uvicorn segue escrevendo no stdout (dev e testes). Com
ela, o log da aplicacao E os do uvicorn (erro e acesso) vao para
`<DASH_LOG_DIR>/dashboard.log`, rotacionado a meia-noite, 30 dias guardados.
"uvicorn" e "uvicorn.access" recebem o handler e deixam de propagar (a raiz ja o
tem: propagar duplicaria a linha); "uvicorn.error" propaga para "uvicorn".
"""

import logging
import logging.handlers
import os
from pathlib import Path

_LOGGERS = ("", "uvicorn", "uvicorn.access")  # uvicorn.error propaga para "uvicorn"
_NOME_HANDLER = "dashboard-arquivo"


def configurar() -> Path | None:
    pasta = os.environ.get("DASH_LOG_DIR")
    if not pasta:
        return None
    destino = Path(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / "dashboard.log"
    # create_app() pode rodar mais de uma vez no mesmo processo (testes): um handler
    # por processo, nunca linhas duplicadas nem arquivo aberto duas vezes.
    if any(h.get_name() == _NOME_HANDLER for h in logging.getLogger().handlers):
        return arquivo
    handler = logging.handlers.TimedRotatingFileHandler(arquivo, when="midnight", backupCount=30,
                                                        encoding="utf-8")
    handler.set_name(_NOME_HANDLER)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    for nome in _LOGGERS:
        logger = logging.getLogger(nome)
        logger.addHandler(handler)
        if nome:
            logger.propagate = False  # senao a raiz grava a mesma linha de novo
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)
    return arquivo
