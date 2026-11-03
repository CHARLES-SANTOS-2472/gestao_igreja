# Roteiro de demonstração

Tempo sugerido: 15 a 20 minutos. Entre como administrador.

## Preparação (antes de apresentar)
1. No Codespace: `git pull`, `python manage.py migrate`, `python manage.py imagens_demo` e, se quiser mais exemplos, `python manage.py carregar_demo`.
2. Reinicie o servidor e confira que a porta 8000 está **Pública** durante a apresentação.
3. Faça login e confirme que as imagens aparecem.

## Sequência
1. **Visão geral**: mensagem da igreja (editável), indicadores e gráficos. Mostre o botão "Editar mensagem".
2. **Membros**: cadastro com foto, cônjuge e filhos vinculados, busca e relatórios. Mostre o consentimento de e-mail e WhatsApp.
3. **Agenda**: calendário, eventos com cartaz, escalas, inscrições e reservas.
4. **Ministérios**: imagem de cada ministério, membros vinculados e reuniões.
5. **Financeiro**: dízimo e oferta com QR-code Pix e "copia e cola", lançamentos, painel, **PDF de prestação de contas**, planilha e **recibo de doação**.
6. **Assistência social**: famílias atendidas, cestas básicas e relatório em PDF (dados protegidos).
7. **Patrimônio**: bens com foto, manutenção, fornecedores e tarefas.
8. **Ocasiões**: datas especiais (Dia das Mães etc.) e como cadastrar uma nova.
9. **Mensagens automáticas**: rodar `python manage.py enviar_mensagens --dry-run` e mostrar o que seria enviado (modo simulação).
10. **Segurança**: usuários e permissões por função, bloqueio após tentativas de senha, **Histórico de alterações** e `python manage.py backup`.

## Pontos a explicar
- Envio real de e-mail e WhatsApp só é ativado com `MESSAGING_LIVE=1` e as credenciais configuradas; na demonstração fica em simulação.
- A assinatura dos pastores será acrescentada depois (`static/img/assinatura.png`).

## Depois da apresentação
- Volte a porta do Codespace para **Privada** e apague o Codespace.
- Mantenha o repositório privado (há fotos de pessoas em `demo_media/`).
