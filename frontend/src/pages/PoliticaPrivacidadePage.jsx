import LegalPageLayout from "../components/legal/LegalPageLayout";

export default function PoliticaPrivacidadePage() {
  return (
    <LegalPageLayout titulo="Política de Privacidade" atualizadoEm="19 de agosto de 2026">
      <p>
        Esta Política de Privacidade descreve como a VisionSaaS trata dados pessoais no uso da
        Plataforma, em conformidade com a Lei Geral de Proteção de Dados (Lei nº 13.709/2018 —
        LGPD). Tratamos três categorias de dados: (1) imagens capturadas pelas câmeras, (2)
        dados de cadastro/login, e (3) dados de pagamento.
      </p>

      <h2>1. Imagens de câmeras — anonimização por padrão</h2>
      <ul>
        <li>
          Todo frame de vídeo processado tem rostos e corpos automaticamente anonimizados
          (Gaussian Blur) <strong>antes</strong> de qualquer exibição ou análise — ninguém, nem a
          equipe da VisionSaaS, visualiza imagens não anonimizadas em operação normal.
        </li>
        <li>
          Não armazenamos vídeo nem recortes de imagem: o processamento é feito em tempo real,
          gerando apenas <strong>métricas agregadas</strong> (contagens, durações, horários) — sem
          nenhum dado biométrico ou de reconhecimento facial.
        </li>
        <li>
          O cliente (sua empresa) é responsável, como controlador dos dados capturados por suas
          câmeras, por eventual sinalização de monitoramento exigida no local físico.
        </li>
      </ul>

      <h2>2. Dados de cadastro e login</h2>
      <ul>
        <li>Coletamos nome, e-mail e senha (armazenada com hash, nunca em texto puro) para criar e autenticar sua conta.</li>
        <li>Usamos o e-mail para comunicações transacionais essenciais: confirmação de cadastro, confirmação de assinatura e avisos de conta.</li>
        <li>Dados de conta são retidos enquanto sua conta estiver ativa, e por prazo adicional quando exigido por obrigação legal.</li>
      </ul>

      <h2>3. Dados de pagamento</h2>
      <p>
        Pagamentos são processados diretamente pela Stripe, nosso parceiro de pagamentos —
        nunca armazenamos número de cartão de crédito em nossos servidores. A Stripe atua como
        operadora desses dados, sob suas próprias políticas de segurança e privacidade
        (PCI-DSS).
      </p>

      <h2>4. Compartilhamento de dados</h2>
      <p>
        Não vendemos dados pessoais. Compartilhamos dados apenas com prestadores necessários à
        operação do serviço (ex.: processamento de pagamento via Stripe, envio de e-mails
        transacionais), sob obrigações contratuais de confidencialidade, ou quando exigido por
        lei.
      </p>

      <h2>5. Seus direitos (art. 18 da LGPD)</h2>
      <p>
        Você pode solicitar, a qualquer momento, confirmação de tratamento, acesso, correção,
        anonimização, portabilidade ou eliminação dos seus dados pessoais, além de revogar
        consentimento, entrando em contato pelo e-mail abaixo.
      </p>

      <h2>6. Segurança</h2>
      <p>
        Adotamos medidas técnicas e organizacionais para proteger os dados tratados, incluindo
        criptografia em trânsito (HTTPS), senhas com hash e isolamento de dados entre empresas
        clientes (multi-tenant).
      </p>

      <h2>7. Contato do Encarregado (DPO)</h2>
      <p>
        Para exercer seus direitos ou tirar dúvidas sobre esta política:{" "}
        <a href="mailto:privacidade@visionsaas.com" className="text-cyan-600 underline dark:text-cyan-400">
          privacidade@visionsaas.com
        </a>
        .
      </p>
    </LegalPageLayout>
  );
}
