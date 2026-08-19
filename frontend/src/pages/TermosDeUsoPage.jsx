import LegalPageLayout from "../components/legal/LegalPageLayout";

export default function TermosDeUsoPage() {
  return (
    <LegalPageLayout titulo="Termos de Uso" atualizadoEm="19 de agosto de 2026">
      <p>
        Estes Termos de Uso ("Termos") regem o acesso e uso da plataforma VisionSaaS
        ("Plataforma", "nós"), um serviço de monitoramento operacional por câmeras com
        inteligência artificial, oferecido no modelo de assinatura (SaaS). Ao criar uma conta
        ou usar a Plataforma, você ("Cliente", "você") concorda com estes Termos.
      </p>

      <h2>1. O serviço</h2>
      <p>
        A Plataforma processa o vídeo das câmeras que você conecta para detectar e rastrear
        pessoas, calcular métricas operacionais (atendimento, ocupação, tempo de permanência)
        e exibir dashboards e relatórios. Rostos e corpos são automaticamente anonimizados
        (borrados) antes de qualquer exibição — ver nossa <a href="/politica-de-privacidade" className="text-cyan-600 underline dark:text-cyan-400">Política de Privacidade</a>.
      </p>

      <h2>2. Cadastro e conta</h2>
      <ul>
        <li>Você deve fornecer informações verdadeiras, completas e atualizadas no cadastro.</li>
        <li>Você é responsável por manter a confidencialidade da sua senha e por toda atividade realizada na sua conta.</li>
        <li>Contas adicionais (equipe) criadas pelo administrador da sua empresa são de sua responsabilidade.</li>
        <li>Reservamo-nos o direito de suspender contas em caso de uso indevido, fraude ou violação destes Termos.</li>
      </ul>

      <h2>3. Assinatura e pagamento</h2>
      <ul>
        <li>Novas contas recebem um período de teste gratuito (trial), sem necessidade de cartão de crédito.</li>
        <li>Após o trial, o acesso às funcionalidades da Plataforma requer uma assinatura paga, processada por nosso parceiro de pagamentos (Stripe).</li>
        <li>A assinatura é recorrente (mensal) e renovada automaticamente até o cancelamento.</li>
        <li>Você pode cancelar a qualquer momento pelo Portal do Cliente, sem multa — o acesso permanece até o fim do período já pago.</li>
        <li>Em caso de falha de pagamento, o acesso às funcionalidades pode ser suspenso até a regularização.</li>
      </ul>

      <h2>4. Uso adequado e responsabilidade sobre as câmeras</h2>
      <ul>
        <li>Você declara ter autoridade legal para instalar e operar as câmeras conectadas à Plataforma, incluindo eventual sinalização exigida por lei em ambientes monitorados.</li>
        <li>É proibido usar a Plataforma para monitorar espaços privados sem consentimento, ou para qualquer finalidade ilícita.</li>
        <li>Você é responsável por garantir que o uso das câmeras, no seu contexto (comércio, escritório, estoque), cumpre a legislação aplicável, incluindo a LGPD.</li>
      </ul>

      <h2>5. Disponibilidade e limitações</h2>
      <p>
        Envidamos esforços razoáveis para manter a Plataforma disponível, mas não garantimos
        operação ininterrupta. Processamento de vídeo em tempo real depende da qualidade e
        estabilidade da conexão das suas câmeras, fora do nosso controle.
      </p>

      <h2>6. Propriedade intelectual</h2>
      <p>
        Todo o software, marca e conteúdo da Plataforma pertencem à VisionSaaS. Os dados
        operacionais gerados pelo uso da sua conta (métricas, relatórios) pertencem a você.
      </p>

      <h2>7. Alterações destes Termos</h2>
      <p>
        Podemos atualizar estes Termos periodicamente. Mudanças relevantes serão comunicadas
        pelo e-mail cadastrado ou por aviso na Plataforma.
      </p>

      <h2>8. Contato</h2>
      <p>
        Dúvidas sobre estes Termos: <a href="mailto:suporte@visionsaas.com" className="text-cyan-600 underline dark:text-cyan-400">suporte@visionsaas.com</a>.
      </p>
    </LegalPageLayout>
  );
}
