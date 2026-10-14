import { useEffect, useState } from "react";
import { api } from "./api";
import Espelho from "./Espelho";
import { BarraEtapas, Etapa } from "./Etapas";
import type { Usuario } from "./Login";
import { ir, Link } from "./rota";
import { Migalhas } from "./Topo";

// Nova medicao (opcao A, 2026-10-09): a etapa 1 do fluxo, antes de a medicao existir. Gerar o espelho cria a
// medicao, e a pagina dela abre na etapa 2 (enviar ao faturamento).

export default function NovaMedicao({ contratoId, usuario }: { contratoId: number; usuario: Usuario }) {
  const podeEditar = usuario.perfil === "engenharia" || usuario.perfil === "admin";
  const [obra, setObra] = useState<string | null>(null);
  useEffect(() => {
    api<{ obra: string; orgao: string }>(`/api/contratos/${contratoId}/cabecalho`).then(c => setObra(c.obra)).catch(() => setObra(""));
  }, [contratoId]);
  useEffect(() => { document.title = `${obra || "Obra"} · Nova medição · grupolotufo`; }, [obra]);

  return (
    <>
      <header className="topbar topbar--detalhe">
        <div className="topbar__trilha">
          <Migalhas itens={[{ rotulo: "Medições", para: { tela: "medicoes" } },
            { rotulo: obra || "Obra", para: { tela: "obra", id: contratoId, aba: "medicoes" } }, { rotulo: "Nova medição" }]} />
        </div>
        <div className="topbar__linha"><h1 className="topbar__titulo">{obra || "Obra"} · Nova medição</h1></div>
      </header>
      <div className="pagina">
        <BarraEtapas atual={1} />
        <Etapa n={1} situacao="atual" resumo="número, competência e os valores informados pelo órgão">
          <Espelho contratoId={contratoId} podeEditar={podeEditar} aoMudar={() => {}} abrirForm
            aoGerar={id => ir({ tela: "medicao", obra: contratoId, id }, { secao: "etapa-2" })}
            semRegra={<p className="cartao__corpo">Esta obra ainda não gera o espelho pelo sistema: lance a medição à mão na{" "}
              <Link para={{ tela: "obra", id: contratoId, aba: "medicoes" }}>página da obra</Link>.</p>} />
        </Etapa>
        {[2, 3, 4, 5].map(n => <Etapa key={n} n={n} situacao="futura" />)}
      </div>
    </>
  );
}
