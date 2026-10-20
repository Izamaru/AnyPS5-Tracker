# AnyPS5 Tracker para Android v0.2.1

Monitor independente criado por [@Izamaru](https://github.com/Izamaru), com créditos ao [AnyPS5](https://github.com/boykopovar/AnyPS5), a [@boykopovar](https://github.com/boykopovar) e aos [contribuidores](https://github.com/boykopovar/AnyPS5/graphs/contributors). Consulte [fontes e atribuições](../CREDITS.md) e a [licença MIT do código original do Tracker](../LICENSE).

App pessoal para Android 8.0 ou superior, com Android System WebView atualizado. O APK é gerado em `../AnyPS5-Tracker/releases/AnyPS5-Tracker-Android-v0.2.1.apk`.

A pasta `android` fica ao lado de `AnyPS5-Tracker`. As ferramentas pesadas (`.tools`), os arquivos de compilação (`build`) e a chave (`keystore`) permanecem aqui. O visual é lido de `../AnyPS5-Tracker/painel-template.html`, e os APKs prontos vão para `../AnyPS5-Tracker/releases`.

O celular consulta diretamente o progresso e o histórico oficiais, além de releases e commits públicos do GitHub. O PC pode ficar desligado. A primeira consulta precisa de internet; depois, a última leitura salva pode ser visualizada offline.

O app atualiza ao abrir e enquanto estiver em uso. O seletor oferece 5, 15 e 30 minutos, 1, 2, 3 e 6 horas. Ao retornar ao app após mais de um minuto, ele faz uma nova consulta. Os temporizadores ficam pausados quando o app sai de primeiro plano; não há serviço ou agendamento em segundo plano. As datas usam o horário local do celular.

Gráfico diário quantitativo, com linhas de funções implementadas e declaradas, comparação com ontem usando o histórico oficial, busca nas bibliotecas e filtros de alterações acompanham o painel desktop. O histórico local do celular é independente do PC.

A versão 0.2.1 muda o gráfico para quantidades absolutas, com escala automática a partir de zero. Instale este APK por cima da versão 0.2.0 para atualizar mantendo os dados; a assinatura e o identificador do aplicativo foram preservados.

## Instalação

1. Copie o APK da pasta `AnyPS5-Tracker/releases` para o celular, por USB ou pelo meio de transferência que preferir.
2. Abra o arquivo no Android e conclua a instalação. Se o sistema solicitar, autorize esse aplicativo de arquivos a instalar este APK.
3. Abra **AnyPS5 Tracker** na lista de aplicativos e mantenha a internet disponível para a primeira leitura.

O APK usa apenas a permissão de internet. Não solicita acesso a arquivos compartilhados, contatos, localização ou notificações. Os dados ficam no armazenamento privado do app; removê-lo apaga sua cópia local. Não há login, conta ou sincronização com o PC.

## Compilação no Windows

Requer Python 3.10+ e Node.js para os testes. Execute os comandos abaixo na pasta que contém `android` e `AnyPS5-Tracker`. Os scripts resolvem os caminhos pela própria localização, independentemente da pasta atual do terminal. As ferramentas portáteis são obtidas de Microsoft e Google, sem instalação global:

```powershell
python android/download_tools.py
python android/prepare_assets.py
node AnyPS5-Tracker/tests/test_android_mobile.js
python android/build_apk.py
```

O compilador usa OpenJDK 17, SDK Android 35, aapt2, D8, zipalign e apksigner. A build verifica a assinatura e grava um arquivo SHA-256 ao lado do APK. Os checksums publicados no repositório oficial do Android são conferidos ao baixar o SDK.

A chave pessoal fica em `android/keystore/personal-debug.jks` (alias `androiddebugkey`, senha de desenvolvimento `android`). Preserve esse arquivo para instalar futuras versões por cima da atual. Esta é uma assinatura para instalação pessoal; publicação em loja precisa de uma configuração de assinatura de produção.

`prepare_assets.py` extrai o visual e os controles do `painel-template.html`. `mobile.js` implementa a coleta e a apresentação móveis sem Python no celular. `MainActivity.java` exibe apenas os arquivos empacotados sob uma origem HTTPS local; links oficiais são enviados ao navegador. Acesso a `file://`, conteúdo local externo e HTTP sem TLS ficam desativados. Nenhuma interface JavaScript com acesso nativo é exposta.

Validação realizada: compilação Java/DEX, assinatura APK v2/v3, manifesto/permissões e testes de coleta/renderização. O funcionamento em aparelho físico ainda precisa ser confirmado.
