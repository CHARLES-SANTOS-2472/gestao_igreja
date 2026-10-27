# Memória do projeto — Gestão da Igreja

Resumo para retomar o trabalho rapidamente. Atualizar ao final de cada etapa.

## Como executar

```powershell
cd "G:\Meu Drive\PYTHON - LIRA - HASHTAG\CODIGOS\gestao_igreja"
& "C:\Users\charles_santos\AppData\Local\Programs\Python\Python310\python.exe" manage.py runserver 127.0.0.1:8000
```

Acesso: http://127.0.0.1:8000/ · Testes: `python manage.py test` (144 passando em 27/10/2026).

## Stack

Django 5.2, Python 3.10, SQLite, ReportLab (PDFs). Apps: `membros`, `eventos`, `ministerios`, `financeiro`, `patrimonio`, `assistencia_social`.

## Já implementado

- Membros, visitantes, família (cônjuge/filhos vinculados), CBO, endereço estruturado.
- Agenda, escalas, inscrições, reservas de espaços.
- Ministérios, atividades, presenças e escalas.
- Financeiro: lançamentos, contas, categorias, relatórios, doações (dinheiro gera receita única; bens sem estoque; destinação única por registro; cancelamento auditado).
- Patrimônio, fornecedores, contratos, tarefas administrativas.
- Assistência social: famílias, ajudas, relatório em PDF timbrado.
- Visão geral: painel com atalhos por permissão, espaço para mensagem e imagem, cartões alternando verde suave e dourado.

## Decisões

- Dados sensíveis (doador, finanças, pastoral) só para quem tem permissão.
- Doação em dinheiro: criar/cancelar somente pela área de Doações.
- Relatórios devem ser PDF com papel timbrado (verde e dourado do sistema).

## Pendências

- Nome oficial, logotipo e contatos da igreja (papel timbrado e painel).
- Mensagem e imagens da Visão geral (espaços já reservados).
- Integração de e-mail/WhatsApp (boas-vindas, aniversários às 7h): aguardam credenciais.
- QR Code Pix de dízimos e ofertas, e dashboard financeiro.
- PDFs dos demais relatórios (financeiro, presenças, membros).
- Estoque e distribuição de bens doados (decisão futura).
- Backup e portal do membro.
