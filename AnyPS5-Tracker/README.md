# AnyPS5 Tracker — guia para Windows

Bot independente para rastrear os **avanços do AnyPS5**, com foco em tecnologia necessária para executar **Ghost of Yōtei no PC**.

Criado por [@Izamaru](https://github.com/Izamaru). Créditos ao [AnyPS5](https://github.com/boykopovar/AnyPS5), a [@boykopovar](https://github.com/boykopovar) e aos [contribuidores do projeto original](https://github.com/boykopovar/AnyPS5/graphs/contributors), responsáveis pelo desenvolvimento e pelos números oficiais. Consulte [créditos e fontes](../CREDITS.md) e a [licença MIT do Tracker](../LICENSE).

**Fonte principal**: https://boykopovar.github.io/AnyPS5/progress.json

A página `progress.html` fornece os números, mas é o JSON oficial que permite identificar funções novas/alteradas sem análise visual da página. Os dados são atualizados pelo próprio projeto após commits em `main`.

## O que monitora

- Número de funções do sistema implementadas, total de funções declaradas e percentual.
- Contagem de instruções da GPU reconhecidas por grupo.
- Alterações nas bibliotecas, inclusive nomes de novas funções implementadas.
- Últimas **releases** e **commits relevantes** (Ghost of Yōtei, Vulkan, shaders, memória, renderização, desempenho etc.).
- Histórico local de checagens em `dados/historico.jsonl` e painel HTML local `painel.html`.
- Alertas por Discord ou Telegram **se você configurar o serviço**; caso contrário, mudanças aparecem no console e no painel.

**Limitações:** métricas de cobertura não indicam a porcentagem de jogos jogáveis. O AnyPS5 pode reconhecer 100% das instruções listadas sem traduzir todas corretamente. As funções declaradas são apenas um subconjunto das APIs do PS5; algumas implementações contabilizadas ainda são simplificadas. O bot não monitora automaticamente comentários de GitHub Discussions; use o link de acompanhamento indicado abaixo.

## Como usar no Windows

Também há uma versão para **Android 8.0+**, que consulta os dados diretamente no celular e funciona com o PC desligado. O APK fica em `releases/AnyPS5-Tracker-Android-v0.2.1.apk`; veja instalação e compilação em [android/README.md](../android/README.md). O código Android e suas ferramentas ficam na pasta irmã `../android`, separados desta pasta do Tracker para PC.

1. Instale **Python 3.10+** (marque a opção de adicionar ao PATH).
2. Descompacte esta pasta em um local definitivo, por exemplo `C:\Projetos\AnyPS5-Tracker`.
3. Execute `INICIAR.bat`.
4. Na primeira execução, o bot estabelece uma linha de base. A partir da segunda, mostra **apenas as diferenças**.
5. Abra `painel.html` no navegador para ver o progresso e as alterações mais recentes.

O cartão de funções das bibliotecas PS5 compara o total atual com o **registro de ontem no histórico oficial** ([history.json](https://boykopovar.github.io/AnyPS5/history.json), usado pela página [history.html](https://boykopovar.github.io/AnyPS5/history.html)). Ontem é calculado pelo calendário local do computador; a data publicada no histórico oficial é usada literalmente, sem convertê-la de fuso. Se não houver registro oficial para ontem, o cartão usa a última medição local sem avisos daquele dia, identificada como “histórico local”. Se nenhuma fonte tiver a data, mostra “Sem medição do dia anterior”.

O histórico oficial é consultado em cada coleta e fica salvo em `dados/estado.json`, permitindo gerar o painel offline. Se a consulta falhar, a última cópia é preservada e o cartão identifica “histórico oficial (salvo)”, com um aviso da coleta. Os registros oficiais correspondem ao último commit de cada dia com atividade, e o projeto recalcula a série com as regras atuais de contagem; não são medições feitas pelo Tracker.

O gráfico de evolução e sua tabela mostram **um registro por dia**, com até 60 dias com dados na visualização. O gráfico usa **quantidades absolutas**: linha contínua para funções implementadas e linha tracejada para declaradas, numa escala comum que parte de zero e cresce conforme o maior total exibido. Assim, declarar novas funções não reduz artificialmente a linha de implementações. Revisões reais nos números continuam aparecendo. Os percentuais permanecem disponíveis nos cartões e na tabela.

Nos dias anteriores, o histórico oficial tem prioridade; em datas sem registro oficial, é usada a última medição local daquele dia. O dia atual mostra a leitura mais recente e é identificado como **Hoje · parcial**, sendo atualizado sem criar novos pontos a cada consulta. As datas oficiais futuras em relação ao calendário local ainda não aparecem. Cada linha identifica sua fonte. O arquivo local de consultas é preservado para comparação entre coletas e registro das alterações.

O painel também inclui busca e ordenação de bibliotecas e filtros de alterações por tipo. A seção “Leitura do progresso” continua explicando a variação da última checagem. Todas as alterações da última checagem ficam disponíveis no botão **Mostrar mais**. A busca por nome alcança todas as bibliotecas; você também pode filtrar as prioritárias, concluídas ou com pendências.

Para aplicar mudanças de visual usando os dados já salvos, sem acessar a internet, alterar o histórico ou enviar alertas:

```powershell
py -3 tracker.py --render-only
```

Depois, recarregue `painel.html` no navegador uma vez para carregar a versão nova. Na área à direita do gráfico, **Atualização do painel** permite escolher **5 minutos (padrão), 15 minutos, 30 minutos, 1 hora, 2 horas, 3 horas ou 6 horas**. A mudança reinicia o tempo de espera e mostra a próxima recarga. A preferência fica salva neste navegador quando o armazenamento local está disponível, com alternativa no armazenamento da aba. A recarga preserva busca, filtros, quantidade de alterações abertas e posição de leitura quando o navegador permite armazenamento de sessão.

Esse seletor controla a recarga da página. A coleta de novos dados continua no intervalo configurado no Agendador do Windows (atualmente 5 minutos). O HTML é independente de rede: a coleta é feita pelo Python. As datas são exibidas no horário local do computador que gera o painel.

Para **coletar novos dados a cada 5 minutos**, execute `INSTALAR-BOT-5MIN.bat` uma vez. Ele usa o Agendador de Tarefas do Windows e inicia uma coleta imediatamente. As próximas coletas rodam em segundo plano enquanto o computador estiver ligado, com internet e sua sessão do Windows estiver conectada; a tela pode estar bloqueada. O painel pode ficar aberto ou fechado. Ao voltar de uma suspensão, o agendador pode executar a coleta pendente; não há coleta enquanto o PC está desligado.

O agendamento usa a tarefa **AnyPS5 Tracker**, evita execuções simultâneas pelo agendador e grava o resultado da última execução em `dados/ultima-execucao.log`. O modo automático atualiza os arquivos locais sem enviar notificações externas. Para desativar, execute `REMOVER-BOT.bat` (o antigo `REMOVER-BOT-6H.bat` também funciona). A alternativa `INSTALAR-BOT-6H.bat` configura a mesma tarefa para 6 horas; instalar uma frequência substitui a anterior.

O agendamento documentado aqui é local ao Windows. Este repositório não fornece um serviço de monitoramento em nuvem ou uma automação vinculada ao ChatGPT. Se mover a pasta depois de instalar o agendamento, execute novamente o instalador para atualizar os caminhos da tarefa.

## Notificações opcionais

No PowerShell, antes de executar o script (as configurações valem apenas para a sessão atual):

```powershell
$env:ANYPS5_DISCORD_WEBHOOK = 'https://discord.com/api/webhooks/SEU_ID/SEU_TOKEN'
py -3 tracker.py --once
```

Ou Telegram:

```powershell
$env:ANYPS5_TELEGRAM_BOT_TOKEN = 'SEU_TOKEN'
$env:ANYPS5_TELEGRAM_CHAT_ID = 'SEU_CHAT_ID'
py -3 tracker.py --once
```

Para agendamento automático do Windows, as variáveis precisam estar disponíveis ao processo agendado, por exemplo nas variáveis de ambiente **do usuário**. **Não cole tokens em repositórios públicos** nem envie suas credenciais por chat. Você pode usar o modo sem notificações, que registra localmente os eventos.

Sem token GitHub o bot usa a API pública, sujeita a limite de requisições. Opcional: `GITHUB_TOKEN` no ambiente para ampliar o limite. Não forneça ao bot permissões desnecessárias.

## Principais URLs

- Página oficial: https://boykopovar.github.io/AnyPS5/progress.html
- Dados JSON: https://boykopovar.github.io/AnyPS5/progress.json
- Histórico: https://boykopovar.github.io/AnyPS5/history.html
- Repositório: https://github.com/boykopovar/AnyPS5
- Ghost of Yōtei — discussão: https://github.com/boykopovar/AnyPS5/discussions/675

## Arquivos

- `tracker.py`: coletor, comparação e emissão de alertas.
- `dashboard.py` e `painel-template.html`: geração e visual do painel; devem acompanhar o script na mesma pasta. O HTML gerado pode ser aberto sozinho.
- `INICIAR.bat`: primeira execução e consulta manual.
- `INSTALAR-BOT-5MIN.bat`: coleta automática a cada 5 minutos no Windows.
- `INSTALAR-BOT-6H.bat`: alternativa de coleta a cada 6 horas.
- `REMOVER-BOT.bat` e `REMOVER-BOT-6H.bat`: removem a tarefa agendada.
- `instalar_agendamento.ps1` e `executar_agendado.ps1`: instalação e execução em segundo plano, com log local.
- `painel-exemplo.html`: visualização ilustrativa dos dados consultados em 13/10/2026 (não é um painel ao vivo).
- `painel.html`: gerado a partir de coleta real ao executar o bot.
- `dados/`: criado automaticamente para salvar estado e histórico.
- `tests/test_tracker.py`: testes automatizados com dados artificiais, sem precisar de internet.

## Testes

```powershell
py -3 -m unittest discover -s tests -v
```

Para verificar os filtros e a paginação do painel, se tiver Node.js instalado:

```powershell
node tests/test_dashboard_ui.js
```

Este projeto não contém dados do jogo nem distribui código-fonte do AnyPS5. É um monitor independente criado para acompanhar informações públicas. Não é afiliado aos mantenedores do AnyPS5.
