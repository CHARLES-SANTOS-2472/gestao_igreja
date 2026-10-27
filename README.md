# Gestão da Igreja

Sistema web responsivo para computador e celular. Esta versão contém acesso autenticado, painel administrativo, cadastro pesquisável de membros, congregados, visitantes e novos convertidos, e gestão básica de cultos e eventos.

## Tecnologia

- Django para autenticação, permissões, formulários e persistência.
- SQLite para desenvolvimento local. Antes de hospedar e cadastrar dados reais, configurar PostgreSQL e uma infraestrutura protegida.
- HTML/CSS responsivos, sem dependência de CDN ou de conexão externa para a interface.

## Executar localmente no Windows

No PowerShell, dentro desta pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py importar_cbo
python manage.py createsuperuser
python manage.py runserver
```

Abra `http://127.0.0.1:8000/` no navegador. Entre com a conta criada como superusuário. No painel `/admin/`, crie usuários da equipe e conceda somente as permissões necessárias. Os acessos a cadastros exigem login e a permissão correspondente.

## Usuários e perfis

Em **Usuários** (menu, visível para administradores) cadastram-se os acessos ao sistema:

- **Super administrador**: o superusuário criado com `createsuperuser`. Cria Administradores e gerencia todos os demais.
- **Administrador**: acesso total aos módulos e gestão de usuários comuns.
- **Usuário comum**: acesso por módulo (consultar, ou consultar/cadastrar/editar).

Usuários são desativados, não excluídos. Cada pessoa troca a própria senha em "Alterar senha".

## Configuração para publicação

- Defina `DJANGO_SECRET_KEY` por variável de ambiente; não use o valor padrão fora do desenvolvimento.
- O banco `db.sqlite3` e dados reais nunca devem ser versionados.
- Instalação: `pip install -r requirements.txt`, `python manage.py migrate`, `python manage.py createsuperuser`, `python manage.py runserver`.

## Escopo desta etapa

- Busca por nome, CPF, e-mail e celular, filtro por situação e paginação.
- O menu separa membros/congregados de visitantes/novos convertidos. A tela de visitantes permite iniciar um cadastro já classificado como visitante, com opção de registrá-lo como novo convertido; os registros existentes continuam no mesmo cadastro de pessoa e podem ser acompanhados/atualizados.
- Visitantes e novos convertidos podem ser promovidos a membros pela lista ou pelo perfil. A ação atualiza o cadastro existente e preenche a data de entrada na igreja somente quando ainda não foi informada.
- Cadastro individual de cada pessoa; vínculos de cônjuge e pais/responsáveis usam os cadastros independentes já existentes.
- O cadastro permite informar, opcionalmente, o nome do cônjuge, dos pais/responsáveis e dos filhos, além de selecionar cadastros existentes. Cada nome novo vira uma pessoa vinculada com situação "Cadastro familiar incompleto"; esse perfil pode ser localizado, completado e atualizado depois. Registros familiares incompletos são sinalizados e não entram nas contagens de pessoas/membros ativos.
- No cadastro, a consulta pública ao ViaCEP preenche logradouro, bairro, cidade e UF após digitar um CEP válido. Somente o CEP digitado é enviado ao serviço; número e complemento continuam manuais. Se a consulta falhar, o endereço ainda pode ser preenchido à mão.
- As datas do cadastro usam e exibem `dd/mm/aaaa`; a edição mantém os valores e vínculos existentes quando não foram enviados no formulário.
- A profissão pode ser escolhida por nome ou código no catálogo CBO 2002 oficial do Ministério do Trabalho e Emprego (busca local, sem depender de internet). O catálogo incluído veio da [página oficial de downloads da CBO](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/cbo/servicos/downloads); para carregá-lo em uma instalação nova ou atualizar os dados, execute `python manage.py importar_cbo`. Também é possível informar uma profissão fora do catálogo.
- Cônjuge, pais/responsáveis e filhos têm seletores separados. Pais e filhos existentes são escolhidos em campos individuais, adicionáveis um por vez. O cadastro aceita ainda marcar uma pessoa como falecida (“In memoriam”) e informar opcionalmente a data de falecimento.
- Registro explícito de consentimento para e-mail e WhatsApp.
- Cultos e eventos com status de publicação, datas, local, capacidade informativa e inscrições.
- Programação por horário, escalas de serviço, registro de visitantes e controle de presença.
- Cadastro administrativo de espaços/equipamentos e reservas, com validação de horários conflitantes.
- As listas de pessoas escaladas e inscritas exigem permissões próprias (`view_eventassignment` e `view_eventregistration`); eventos e cadastros de pessoas também possuem permissões independentes.
- Nenhum e-mail ou mensagem de WhatsApp é enviado por esta versão. Disparos precisam de consentimento verificável, configuração de provedores, credenciais protegidas, modelos aprovados e processamento agendado.
- Departamentos e ministérios permitem cadastrar nome, descrição, líder, vice-líder e participantes. A composição segue as mesmas funções em todos os ministérios; líderes e vice-líderes também ficam vinculados como membros da equipe. Reuniões e atividades podem ser registradas por departamento, com data, horário, local, responsável, observações e participantes. A presença dos participantes pode ser marcada como presente, ausente ou não registrada, e há relatório resumido por departamento. Cada atividade também permite registrar pessoas escaladas para pregação, direção, música, recepção, apoio, intercessão ou outra função. As permissões de visualização, registro de presença e gestão de escalas são independentes.
- O primeiro módulo financeiro registra receitas e despesas, categorias, contas, valores previstos, liquidações, associações opcionais a ministérios/eventos e histórico de alterações. Os lançamentos podem identificar Pix, cartão de crédito, dinheiro, transferência bancária ou outra forma; os relatórios agrupam os valores liquidados também por forma. Registre dízimos e ofertas na categoria correspondente e confirme o recebimento somente depois da conferência do tesoureiro. Contas bancárias armazenam banco, agência, número/tipo de conta e titularidade; para PJ, também CNPJ e um representante legal (nome e CPF). O número integral e os documentos do titular ficam disponíveis somente na área de contas para usuários com permissão financeira; as listagens mascaram o número da conta. O painel separa totais recebidos/pagos de pendências e calcula saldo por conta; relatórios filtram períodos e agrupam valores por categoria, forma de recebimento/pagamento, ministério e evento. O cadastro de doações registra individualmente dinheiro (doador opcional/anônimo, valor, conta, forma e destino) e bens (descrição, quantidade, unidade e destino). Cada registro tem uma destinação; para repartir uma contribuição, registre cada parte separadamente. Doações em dinheiro criam uma única receita vinculada à categoria “Doações”, evitando lançamento duplicado no financeiro; o nome do doador não é copiado para a descrição dessa receita. Doações de bens são registradas sem valor financeiro e, nesta etapa, sem controle de estoque. Registros recebidos não são editados: correções são feitas por cancelamento com motivo; a receita financeira vinculada também é cancelada e auditada. O cadastro exige `view_donationrecord` e `add_donationrecord`; dinheiro também exige `add_financialtransaction` e `view_financialaccount`. O cancelamento requer `change_donationrecord` e, para doações em dinheiro, `change_financialtransaction`. No admin, conceda somente as permissões financeiras necessárias (`view_financialtransaction`, `add_financialtransaction`, `change_financialtransaction`, `view_financialcategory`, `add_financialcategory`, `change_financialcategory`, `view_financialaccount`, `add_financialaccount` e `change_financialaccount`). Categorias iniciais são criadas pela migração. Não há processamento de cartão, confirmação automática Pix ou armazenamento de comprovantes; essas integrações dependem da escolha e configuração de provedores e ficam para uma fase posterior.
- O módulo Patrimônio registra instrumentos, móveis, computadores, equipamentos, veículos e imóveis, com número patrimonial, série, localização, situação, aquisição e observações. O histórico de manutenção registra serviço, custo, responsável e próxima data; a lista permite pesquisar os bens. Fornecedores podem ser cadastrados com razão social, CNPJ opcional e contato. Contratos são vinculados a fornecedores e registram vigência, valor e situação; a listagem destaca contratos que vencem nos próximos 30 dias e separa os vencidos. Tarefas administrativas permitem registrar prazo, prioridade, situação e usuário responsável; o painel mostra tarefas atribuídas ao usuário, prazos nos próximos sete dias e itens atrasados. Os detalhes da tarefa exibem o histórico de criação e alterações com os dados anteriores e posteriores. O campo de descrição orienta a não registrar dados pastorais, sensíveis ou credenciais. Essas indicações aparecem ao consultar as áreas, sem envio automático de avisos. As permissões de bens (`view_churchasset`, `add_churchasset`, `change_churchasset`), manutenção (`view_assetmaintenance`, `add_assetmaintenance`), fornecedores (`view_supplier`, `add_supplier`, `change_supplier`), contratos (`view_contract`, `add_contract`, `change_contract`) e tarefas (`view_administrativetask`, `add_administrativetask`, `change_administrativetask`) são independentes. Uma próxima manutenção não pode ser marcada antes da data do serviço, e o fim de vigência não pode ser anterior ao início.
- A área de Assistência Social registra famílias para atendimento, com identificação de referência, contato e endereço separado em CEP, logradouro, número, complemento, bairro, cidade e UF. A busca de CEP usa o ViaCEP e envia somente o CEP digitado; os demais dados do endereço não são enviados a essa consulta. A ficha pode abrir um botão do Google Maps somente após clique, com aviso de que o endereço será compartilhado com esse serviço externo; nenhum mapa é incorporado ou carregado automaticamente. Endereços existentes no campo anterior são preservados durante a atualização. A área também controla ajudas programadas, entregues ou canceladas, como cestas básicas, alimentos, itens de higiene, roupas e ajuda financeira. A ajuda financeira exige valor; para os demais itens, informa-se quantidade. O histórico pode ser filtrado por período, tipo e situação e apresenta totais e resumo por tipo de ajuda de acordo com os filtros aplicados; o relatório pode ser baixado em PDF com cabeçalho visual do sistema, paginação, totais e filtros utilizados. O espaço para nome, logotipo e contatos oficiais da igreja está reservado para configuração futura. O relatório respeita as permissões de consulta. A família e os registros não são vinculados automaticamente aos cadastros de membros ou ao atendimento pastoral. A consulta de ajudas tem permissão própria e as ações de criação e edição também são separadas (`view_assistedfamily`, `add_assistedfamily`, `change_assistedfamily`, `view_assistancerecord`, `add_assistancerecord`, `change_assistancerecord`). Descrições devem limitar-se a informações operacionais; não registrar diagnósticos, relatos pastorais ou documentos pessoais. Esse módulo inicial não guarda comprovantes, não processa pagamentos e não substitui uma avaliação de privacidade/LGPD.
- Ainda não há portal de autoatendimento para membros, confirmação pública de inscrições, integração com calendário externo ou atendimento pastoral. O módulo financeiro atual não processa pagamentos Pix nem guarda anexos de comprovantes.

## Antes de usar com dados reais

Este projeto é um início de desenvolvimento, não uma instalação pronta para produção. Dados como CPF, contatos e informações familiares são pessoais. Configure HTTPS, uma chave `DJANGO_SECRET_KEY` forte fora do código, `DJANGO_DEBUG=0`, hosts permitidos, PostgreSQL, backups criptografados, controle de acesso por função, política de retenção e procedimentos de resposta a incidentes. Restrinja dados pastorais e financeiros em módulos próprios antes de implementá-los. Avalie a LGPD, a base legal e os avisos de privacidade com orientação adequada.

Para produção, defina `DJANGO_ALLOWED_HOSTS` como uma lista separada por vírgulas de domínios confiáveis. Não publique o banco SQLite de desenvolvimento nem use credenciais reais de membros em testes.

## Recuperação de senha

Na tela de login, **Esqueci minha senha** envia um link (válido por 1 hora) ao e-mail cadastrado no usuário. Sem SMTP configurado, o e-mail é exibido no terminal do servidor. Para envio real, defina EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend, EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD e DEFAULT_FROM_EMAIL.
