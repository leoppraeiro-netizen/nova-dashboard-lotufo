"""Apoio dos testes de corrida (TOCTOU deterministico), unico lugar.

Desde a fase 3 a mutacao inteira roda sob BEGIN IMMEDIATE (db.mutacao), entao a outra conexao nao
consegue escrever no meio dela. A corrida e' encenada de fora: a interferencia commita antes da
chamada sob teste, e a conexao abaixo devolve ao codigo a leitura OBSOLETA tirada antes. Quem barra
o perdedor e' o UPDATE/INSERT condicional (ou o UNIQUE), nao a validacao em Python.
"""


class CursorMaterializado:
    """Cursor ja lido: devolve as linhas capturadas antes da corrida."""
    def __init__(self, linhas):
        self._linhas = linhas

    def fetchone(self):
        return self._linhas[0] if self._linhas else None

    def fetchall(self):
        return self._linhas


class ConexaoComCorrida:
    """Devolve, UMA vez, a leitura obsoleta no lugar do primeiro SQL interceptado.

    `trecho` identifica o SQL (sem diferenca de caixa): com `no_inicio=True` precisa abri-lo,
    senao basta aparecer nele.
    """
    def __init__(self, real, linhas_antigas, trecho: str, no_inicio: bool = False):
        self._real, self._linhas, self._armada = real, linhas_antigas, True
        self._trecho, self._no_inicio = trecho.upper(), no_inicio

    def execute(self, sql, params=()):
        s = sql.upper()
        casa = s.lstrip().startswith(self._trecho) if self._no_inicio else self._trecho in s
        if self._armada and casa:
            self._armada = False
            return CursorMaterializado(self._linhas)
        return self._real.execute(sql, params)

    def __getattr__(self, nome):
        return getattr(self._real, nome)
