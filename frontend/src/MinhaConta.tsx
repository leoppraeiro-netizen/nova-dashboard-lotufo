import { useEffect, useRef, useState } from "react";
import { api, apiForm, mensagemDeErro } from "./api";
import ConfirmarRemocao from "./ConfirmarRemocao";
import type { Usuario } from "./Login";
import Selo from "./Selo";

type Login = { estado: string; user_code: string | null; verification_uri: string | null; erro?: string };
type Status = { configurado: boolean; conectado: boolean; login: Login; assinatura: boolean };

export default function MinhaConta({ usuario }: { usuario: Usuario }) {
  // B-09 (10/10/2026): a diretoria nao manda e-mail pela dashboard: ve o e-mail de login e troca a senha
  const podeEditar = usuario.perfil === "engenharia" || usuario.perfil === "admin";
  const [st, setSt] = useState<Status | null>(null);
  const [erro, setErro] = useState("");
  const [teste, setTeste] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [trocandoSenha, setTrocandoSenha] = useState(false);   // so' o botao da troca de senha muda o rotulo
  const timer = useRef<number | undefined>(undefined);
  const arquivo = useRef<HTMLInputElement>(null);
  const [versao, setVersao] = useState(() => Date.now());
  // A-05/B-10 (10/10/2026): trocar a propria senha, com erro e aviso proprios do bloco
  const [senha, setSenha] = useState({ atual: "", nova: "", confirmar: "" });
  const [erroSenha, setErroSenha] = useState("");
  const [senhaTrocada, setSenhaTrocada] = useState("");

  const carregar = () => api<Status>("/api/correio/status").then(setSt).catch(e => setErro(mensagemDeErro(e)));
  useEffect(() => { if (podeEditar) carregar(); return () => window.clearInterval(timer.current); }, [podeEditar]);

  // Enquanto a Microsoft espera a pessoa digitar o codigo, consultar o estado a cada 5 s.
  useEffect(() => {
    window.clearInterval(timer.current);
    if (st?.login.estado === "aguardando") timer.current = window.setInterval(carregar, 5000);
  }, [st?.login.estado]);

  async function conectar() {
    setErro(""); setOcupado(true);
    try { setSt(await api<Status>("/api/correio/conectar", { method: "POST" })); }
    catch (e) { setErro(mensagemDeErro(e)); }
    finally { setOcupado(false); }
  }

  async function enviarTeste() {
    setErro(""); setTeste(""); setOcupado(true);
    try {
      const r = await api<{ remetente: string }>("/api/correio/teste", { method: "POST" });
      setTeste(`E-mail de teste enviado para ${r.remetente}. Confira a caixa de entrada e os itens enviados.`);
    } catch (e) { setErro(mensagemDeErro(e)); }
    finally { setOcupado(false); }
  }

  async function subirAssinatura(ev: React.ChangeEvent<HTMLInputElement>) {
    const f = ev.target.files?.[0];
    if (f) await enviarImagem(f);
  }

  // Colar (Ctrl+V) ou arrastar a imagem: o Outlook na web nao deixa salvar a imagem da assinatura.
  function imagemDe(dados: DataTransfer | null): File | null {
    const f = [...(dados?.files ?? [])].find(x => x.type === "image/png" || x.type === "image/jpeg");
    return f ?? null;
  }

  async function enviarImagem(f: File) {
    setErro(""); setOcupado(true);
    try {
      const fd = new FormData(); fd.append("arquivo", f);
      setSt(await apiForm<Status>("/api/correio/assinatura", fd));
      setVersao(Date.now());
    } catch (e) { setErro(mensagemDeErro(e)); }
    finally { setOcupado(false); if (arquivo.current) arquivo.current.value = ""; }
  }

  function colar(ev: React.ClipboardEvent<HTMLDivElement>) {
    const f = imagemDe(ev.clipboardData);
    if (f) { ev.preventDefault(); void enviarImagem(f); }
    else setErro("A área de transferência não tem imagem. Copie a imagem da assinatura (ou o arquivo) e cole de novo.");
  }

  async function removerAssinatura() {
    setErro(""); setOcupado(true);
    try { setSt(await api<Status>("/api/correio/assinatura", { method: "DELETE" })); }
    catch (e) { setErro(mensagemDeErro(e)); }
    finally { setOcupado(false); }
  }

  async function trocarSenha(ev: React.FormEvent) {
    ev.preventDefault();
    setErroSenha(""); setSenhaTrocada("");
    if (senha.nova !== senha.confirmar) { setErroSenha("A confirmação não bate com a senha nova."); return; }
    setOcupado(true); setTrocandoSenha(true);
    try {
      await api("/api/auth/senha", { method: "POST", body: JSON.stringify({ senha_atual: senha.atual, senha_nova: senha.nova }) });
      setSenha({ atual: "", nova: "", confirmar: "" });
      setSenhaTrocada("Senha trocada. As outras sessões abertas com a sua conta foram encerradas.");
    } catch (e) { setErroSenha(mensagemDeErro(e)); }
    finally { setOcupado(false); setTrocandoSenha(false); }
  }

  if (podeEditar && !st) return <p className="vazio">{erro || "Carregando…"}</p>;
  return (
    <>
    {/* gate Sol S6 (10/10/2026): sem e-mail, sem a frase */}
    {!podeEditar && usuario.email && (
      <section className="cartao">
        <header className="cartao__cabeca"><h2 className="cartao__titulo">Sua conta</h2></header>
        <div className="cartao__corpo"><p>Você entra com o e-mail <strong>{usuario.email}</strong>.</p></div>
      </section>
    )}
    {st && <>
    <section className="cartao">
      <header className="cartao__cabeca">
        <h2 className="cartao__titulo">Conta Microsoft</h2>
        {st.conectado ? <Selo classe="selo--ok">Conectada</Selo> : <Selo classe="selo--atencao">Não conectada</Selo>}
      </header>
      <div className="cartao__corpo">
        <p>Os e-mails que você manda pela dashboard saem da sua própria caixa e aparecem nos seus itens enviados.</p>
        {!st.configurado && <p role="alert">O Microsoft 365 ainda não foi configurado neste servidor.</p>}
        {st.login.estado === "aguardando" && st.login.user_code && (
          <p>
            Abra <a href={st.login.verification_uri ?? "#"} target="_blank" rel="noreferrer">{st.login.verification_uri}</a>,
            digite o código <strong>{st.login.user_code}</strong> e entre com a sua conta da Lotufo.
          </p>
        )}
        {st.login.estado === "expirado" && <p role="alert">O código expirou. Peça outro.</p>}
        {st.login.estado === "recusado" && <p role="alert">A Microsoft recusou o acesso. Tente de novo.</p>}
        {st.login.estado === "erro" && <p role="alert">{st.login.erro}</p>}
        {erro && <p role="alert">{erro}</p>}
        <p className={teste ? undefined : "sr-only"} role="status">{teste}</p>
        <div className="acoes acoes--inicio">
          <button type="button" className="btn btn--primario" disabled={ocupado || !st.configurado} onClick={conectar}>
            {st.conectado ? "Conectar de novo" : "Conectar minha conta Microsoft"}
          </button>
          <button type="button" className="btn" disabled={ocupado || !st.conectado}
                  onClick={enviarTeste}>Enviar e-mail de teste</button>
        </div>
        <p className="campo__nota">Conectar de novo também libera as sugestões de contatos da empresa ao escrever o
          destinatário, como no Outlook.</p>
      </div>
    </section>
    <section className="cartao">
      <header className="cartao__cabeca">
        <h2 className="cartao__titulo">Assinatura de e-mail</h2>
        {st.assinatura ? <Selo classe="selo--ok">Cadastrada</Selo> : <Selo>Não cadastrada</Selo>}
      </header>
      <div className="cartao__corpo">
        <p>A imagem da sua assinatura vai no fim de todo e-mail que você manda pela dashboard (PNG ou JPG, até 1 MB).</p>
        <p className="campo__nota">Onde achar a imagem: o Outlook do computador guarda a assinatura em
          {" "}<code className="sem-quebra">%APPDATA%\Microsoft\Signatures</code>, dentro da pasta que termina em “_arquivos” (arquivo
          image001.png). Cole esse endereço na barra da janela de escolher arquivo. Também dá para copiar a imagem e colar
          aqui (Ctrl+V), ou arrastar o arquivo para o quadro abaixo.</p>
        <div className="assinatura-alvo" tabIndex={0} role="button" aria-label="Colar ou arrastar a imagem da assinatura"
             onPaste={colar} onDragOver={ev => ev.preventDefault()}
             onDrop={ev => { ev.preventDefault(); const f = imagemDe(ev.dataTransfer); if (f) void enviarImagem(f); }}>
          Clique aqui e cole a imagem (Ctrl+V), ou arraste o arquivo
        </div>
        {st.assinatura
          ? <img className="assinatura-previa" src={`/api/correio/assinatura?v=${versao}`} alt="Sua assinatura" />
          : <p className="campo__nota">Nenhuma assinatura cadastrada.</p>}
        <div className="acoes acoes--inicio">
          <label className="btn btn--primario">
            {st.assinatura ? "Trocar a imagem" : "Enviar a imagem da assinatura"}
            <input ref={arquivo} type="file" accept="image/png,image/jpeg" className="sr-only" disabled={ocupado}
                   onChange={subirAssinatura} />
          </label>
          {st.assinatura && <ConfirmarRemocao alvo="a assinatura" classe="btn" ocupado={ocupado} aoConfirmar={() => void removerAssinatura()} />}
        </div>
      </div>
    </section>
    </>}
    <section className="cartao">
      <header className="cartao__cabeca">
        <h2 className="cartao__titulo">Trocar senha</h2>
      </header>
      <form className="cartao__corpo form-inline" onSubmit={trocarSenha}>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="senha-atual">Senha atual</label>
          <input id="senha-atual" type="password" required autoComplete="current-password" value={senha.atual}
                 onChange={e => setSenha({ ...senha, atual: e.target.value })} />
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="senha-nova">Senha nova (mínimo de 10 caracteres)</label>
          <input id="senha-nova" type="password" required minLength={10} autoComplete="new-password" value={senha.nova}
                 onChange={e => setSenha({ ...senha, nova: e.target.value })} />
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="senha-confirmar">Confirmar a senha nova</label>
          <input id="senha-confirmar" type="password" required minLength={10} autoComplete="new-password" value={senha.confirmar}
                 onChange={e => setSenha({ ...senha, confirmar: e.target.value })} />
        </div>
        <button type="submit" className="btn btn--primario" disabled={ocupado}>{trocandoSenha ? "Trocando…" : "Trocar senha"}</button>
      </form>
      {erroSenha && <div className="cartao__corpo"><p role="alert">{erroSenha}</p></div>}
      <p className={senhaTrocada ? "cartao__corpo" : "sr-only"} role="status">{senhaTrocada}</p>
    </section>
    </>
  );
}
